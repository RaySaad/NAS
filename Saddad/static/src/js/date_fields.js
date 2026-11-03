/** @odoo-module **/
import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useDateTimePicker } from "@web/core/datetime/datetime_picker_hook";
import { formatDate, formatDateTime } from "@web/core/l10n/dates";
import { useInputField } from "@web/views/fields/input_field_hook";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export function fullDate(value, datetime = false) {
    if (!value) return "";
    return datetime ? formatDateTime(value, { format: "dd/MM/yyyy HH:mm:ss" })
                    : formatDate(value, { format: "dd/MM/yyyy" });
}

export class RecruitmentDate extends Component {
    static props = { ...standardFieldProps };
    static template = xml`<span t-ref="root" dir="ltr">
        <span t-if="props.readonly" t-esc="formattedValue"/>
        <input t-else="" t-ref="start-date" class="o_input" t-att-id="props.id"
               placeholder="DD/MM/YYYY" autocomplete="off"/>
    </span>`;
    setup() {
        const field = this;
        this.picker = useDateTimePicker({
            target: "root",
            format: this.isDatetime ? "dd/MM/yyyy HH:mm:ss" : "dd/MM/yyyy",
            showSeconds: this.isDatetime,
            get pickerProps() {
                return { type: field.isDatetime ? "datetime" : "date",
                         value: field.props.record.data[field.props.name] || false };
            },
            onApply: (value) => this.props.record.update({ [this.props.name]: value }),
        });
    }
    get isDatetime() { return this.props.record.fields[this.props.name].type === "datetime"; }
    get formattedValue() { return fullDate(this.props.record.data[this.props.name], this.isDatetime); }
}

export function hijriDisplay(value) {
    const text = (value || "").replace(/[٠-٩]/g, c => String(c.charCodeAt(0) - 1632));
    const match = text.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);
    return match ? `${match[3].padStart(2, "0")}/${match[2].padStart(2, "0")}/${match[1]}` : text;
}
export function hijriStorage(value) {
    const text = value.trim().replace(/[٠-٩]/g, c => String(c.charCodeAt(0) - 1632));
    const match = text.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
    return match ? `${match[3]}/${match[2].padStart(2, "0")}/${match[1].padStart(2, "0")}` : text;
}
class RecruitmentHijri extends Component {
    static props = { ...standardFieldProps };
    static template = xml`<span dir="ltr">
        <span t-if="props.readonly" t-esc="formattedValue"/>
        <input t-else="" t-ref="input" class="o_input" t-att-id="props.id" placeholder="DD/MM/YYYY"/>
    </span>`;
    setup() {
        useInputField({ getValue: () => this.formattedValue, parse: hijriStorage });
    }
    get formattedValue() { return hijriDisplay(this.props.record.data[this.props.name]); }
}
registry.category("fields").add("saddad_date", { component: RecruitmentDate, supportedTypes: ["date", "datetime"] });
registry.category("fields").add("saddad_hijri", { component: RecruitmentHijri, supportedTypes: ["char"] });
registry.category("formatters").add("saddad_date", (value, options) => fullDate(value, options?.field?.type === "datetime"));
registry.category("formatters").add("saddad_hijri", hijriDisplay);
