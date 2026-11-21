IF NOT EXISTS (SELECT 1 FROM dbo.supplies)
    INSERT INTO dbo.supplies (name, [rule])
    VALUES
        (N'Eggs', N'take_turns'),
        (N'Nespresso pods', N'least_spent'),
        (N'Toilet paper', N'take_turns'),
        (N'Washing-up liquid', N'least_spent');
