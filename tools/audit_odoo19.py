"""Source-only Odoo 19 audit. Never imports Odoo or connects to a database."""
import argparse
import ast
import re
from collections import defaultdict
from pathlib import Path

from lxml import etree


def audit(root, odoo_root, backup):
    roots = [root, odoo_root / 'odoo/addons', odoo_root / 'addons', odoo_root / 'enterprise']
    manifests = {}
    paths = {}
    for base in roots:
        for manifest in base.glob('*/__manifest__.py'):
            name = manifest.parent.name
            if name not in paths:
                paths[name] = manifest.parent
                manifests[name] = ast.literal_eval(manifest.read_text())
    custom = {p.parent.name for p in root.glob('*/__manifest__.py')}
    closure = set()
    errors = []

    def visit(name, trail=()):
        if name in trail:
            errors.append(f'Dependency cycle: {trail + (name,)}')
            return
        if name in closure:
            return
        if name not in paths:
            errors.append(f'Missing dependency: {name}')
            return
        closure.add(name)
        for dep in manifests[name].get('depends', []):
            visit(dep, trail + (name,))

    for name in sorted(custom):
        visit(name)

    fields = defaultdict(set)
    parents = defaultdict(set)
    providers = defaultdict(set)
    relations = {}
    core_methods = defaultdict(set)
    custom_classes = []
    python_count = 0
    xml_count = 0
    for module in sorted(closure):
        for path in paths[module].rglob('*.py'):
            if '__pycache__' in path.parts:
                continue
            if module in custom:
                python_count += 1
            try:
                tree = ast.parse(path.read_bytes(), filename=str(path))
            except SyntaxError as exc:
                errors.append(f'{path}: {exc}')
                continue
            for cls in tree.body:
                if not isinstance(cls, ast.ClassDef):
                    continue
                meta = {}
                local_fields = set()
                for node in cls.body:
                    if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                        continue
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if not isinstance(target, ast.Name):
                            continue
                        if target.id in ('_name', '_inherit', '_inherits'):
                            try:
                                meta[target.id] = ast.literal_eval(node.value)
                            except (ValueError, TypeError):
                                pass
                        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
                            if isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == 'fields':
                                local_fields.add(target.id)
                                call = node.value
                                relation = next((k.value for k in call.keywords if k.arg == 'comodel_name'), None)
                                if relation is None and call.func.attr in ('Many2one', 'One2many', 'Many2many') and call.args:
                                    relation = call.args[0]
                                if isinstance(relation, ast.Constant) and isinstance(relation.value, str):
                                    relations[(cls.name, target.id)] = relation.value
                inherit = meta.get('_inherit', [])
                if isinstance(inherit, str):
                    inherit = [inherit]
                model = meta.get('_name') or (inherit[0] if inherit else None)
                if model:
                    if module not in custom:
                        core_methods[model].update(n.name for n in cls.body if isinstance(n, ast.FunctionDef))
                    for field in local_fields:
                        relation = relations.pop((cls.name, field), None)
                        if relation:
                            relations[(model, field)] = relation
                    fields[model].update(local_fields)
                    fields[model].update({'id', 'display_name', 'create_uid', 'create_date', 'write_uid', 'write_date'})
                    parents[model].update(p for p in inherit if p != model)
                    parents[model].update(meta.get('_inherits', {}).keys())
                    providers[model].add(module)
                    if module in custom and 'tests' not in path.parts:
                        custom_classes.append((module, path, model, cls))

    def model_fields(model, seen=None):
        seen = set() if seen is None else seen
        if model in seen:
            return set()
        seen.add(model)
        result = set(fields[model])
        for parent in parents[model]:
            result.update(model_fields(parent, seen))
        return result

    # Core declares this Python-keyword field with setattr outside the class.
    fields['ir.rule'].add('global')

    generic_methods = set()
    for cls in ast.parse((odoo_root / 'odoo/orm/models.py').read_bytes()).body:
        if isinstance(cls, ast.ClassDef) and cls.name in ('BaseModel', 'Model', 'AbstractModel', 'TransientModel'):
            generic_methods.update(n.name for n in cls.body if isinstance(n, ast.FunctionDef))

    def inherited_core_methods(model, seen=None):
        seen = set() if seen is None else seen
        if model in seen:
            return set()
        seen.add(model)
        result = core_methods[model] | generic_methods
        for parent in parents[model]:
            result = result | inherited_core_methods(parent, seen)
        return result

    def field_relation(model, field, seen=None):
        seen = set() if seen is None else seen
        if model in seen:
            return None
        seen.add(model)
        relation = relations.get((model, field))
        if relation:
            return relation
        for parent in parents[model]:
            relation = field_relation(parent, field, seen)
            if relation:
                return relation
        return None

    def check_arch(node, model, path):
        for child in node:
            child_model = model
            if child.tag == 'xpath':
                # A path through a nested relational view changes its model.
                relational_fields = re.findall(r"field\[@name=['\"]([^'\"]+)['\"]\]/(?:list|form|kanban)", child.get('expr', ''))
                for field in relational_fields:
                    child_model = field_relation(child_model, field) if child_model else None
            if child.tag == 'field' and child.get('name'):
                field = child.get('name')
                if field not in model_fields(model):
                    errors.append(f'{path}:{child.sourceline}: unknown view field {model}.{field}')
                if any(c.tag in ('list', 'form', 'kanban', 'search') for c in child):
                    child_model = field_relation(model, field)
            if child_model:
                check_arch(child, child_model, path)

    def env_model(node):
        while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            node = node.func.value
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == 'env':
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                return node.slice.value
        return None

    def check_create_values(method, path):
        assignments = defaultdict(list)
        for node in ast.walk(method):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assignments[target.id].append(node.value)
        for node in ast.walk(method):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != 'create' or not node.args:
                continue
            model = env_model(node.func.value)
            if model not in providers:
                continue
            arg = node.args[0]
            dictionaries = assignments[arg.id] if isinstance(arg, ast.Name) else [arg]
            for values in dictionaries:
                if not isinstance(values, ast.Dict):
                    continue
                for key in values.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value not in model_fields(model):
                        errors.append(f'{path}:{key.lineno}: unknown create field {model}.{key.value}')

    for module in sorted(custom):
        for section in ('data', 'demo'):
            for filename in manifests[module].get(section, []):
                path = paths[module] / filename
                if not path.is_file():
                    errors.append(f'{module}: missing {section} file {filename}')
        for path in paths[module].rglob('*.xml'):
            xml_count += 1
            try:
                tree = etree.parse(str(path))
            except etree.XMLSyntaxError as exc:
                errors.append(f'{path}: {exc}')
                continue
            for record in tree.xpath('//record[@model]'):
                model = record.get('model')
                if model not in providers:
                    errors.append(f'{path}:{record.sourceline}: unknown model {model}')
                    continue
                valid_fields = model_fields(model)
                for field in record.findall('field'):
                    if field.get('name') not in valid_fields:
                        errors.append(f'{path}:{field.sourceline}: unknown {model}.{field.get("name")}')
                if model == 'ir.ui.view':
                    view_model = record.find('field[@name="model"]')
                    arch = record.find('field[@name="arch"]')
                    if view_model is not None and arch is not None and view_model.text in providers:
                        check_arch(arch, view_model.text, path)
        for _, path, model, cls in (c for c in custom_classes if c[0] == module):
            valid_fields = model_fields(model)
            for method in (n for n in cls.body if isinstance(n, ast.FunctionDef)):
                check_create_values(method, path)
                for call in ast.walk(method):
                    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                        continue
                    owner = call.func.value
                    if isinstance(owner, ast.Call) and isinstance(owner.func, ast.Name) and owner.func.id == 'super':
                        if call.func.attr not in inherited_core_methods(model):
                            errors.append(f'{path}:{call.lineno}: review super method {model}.{call.func.attr}')
                for decorator in method.decorator_list:
                    if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                        continue
                    if decorator.func.attr not in ('depends', 'constrains', 'onchange'):
                        continue
                    for arg in decorator.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            first = arg.value.split('.')[0]
                            if first not in valid_fields:
                                errors.append(f'{path}:{method.lineno}: unknown {model}.{first} in {decorator.func.attr}')
        # Controllers are not ORM model classes, but their create values matter too.
        for path in (paths[module] / 'controllers').glob('*.py'):
            for method in ast.walk(ast.parse(path.read_bytes())):
                if isinstance(method, ast.FunctionDef):
                    check_create_values(method, path)
    if backup:
        missing = [str(p.relative_to(backup)) for p in backup.rglob('*')
                   if p.is_file() and not any(x in ('.git', '__pycache__') for x in p.relative_to(backup).parts)
                   and p.suffix != '.pyc' and not (root / p.relative_to(backup)).is_file()]
        errors.extend(f'Missing backup file: {p}' for p in missing)
    print(f'{len(custom)} custom modules; {python_count} Python files; {xml_count} XML files; {len(closure)} dependency modules')
    for error in sorted(set(errors)):
        print(error)
    print(f'{len(set(errors))} static findings (not an installation or workflow test)')
    return bool(errors)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--odoo-root', type=Path, required=True)
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    raise SystemExit(audit(Path(__file__).resolve().parents[1], args.odoo_root, args.backup))
