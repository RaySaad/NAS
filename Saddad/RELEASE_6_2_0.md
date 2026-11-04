# Saddad 19.0.6.2.0

Resident Import now updates the employee's saddad_iqama_expiry when Apply Ready Rows is selected and the imported row is valid. An empty employee date is filled; an older date is advanced to the report date; an equal or later employee date is preserved. Preview, Reset and Reject do not change employee expiry. Blocked rows remain skipped.

Apply compares the latest employee date under a database lock, including changes made after Preview. Existing employee matching, company/employer mappings, source freshness and Gregorian/Hijri checks remain mandatory. Updates use the authorized Resident HR expiry method, with employee chatter evidence identifying the source import and batch chatter recording the update count. Other employee fields, renewal completion and accounting are unchanged.

Upgrade the complete Saddad addon without uninstalling. Existing Applied imports are not replayed. For an existing Preview, reset and preview again to refresh the explanatory summary, then Apply Ready Rows. For previously Applied imports, create a new import from a current original report. Configure the report's employer numbers under Muqeem Establishments for the import company before previewing.

English and Arabic user manuals revision 1.1 accompany this release.
