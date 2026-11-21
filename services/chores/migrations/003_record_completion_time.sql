-- Existing completions have a date but no known time of entry.
-- The default records the UTC insertion time for new completions.
ALTER TABLE dbo.chore_log
    ADD recorded_at_utc DATETIME2(0) NULL
        CONSTRAINT DF_chore_log_recorded_at_utc DEFAULT (SYSUTCDATETIME());
