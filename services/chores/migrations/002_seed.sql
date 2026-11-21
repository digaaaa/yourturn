IF NOT EXISTS (SELECT 1 FROM dbo.roommates)
    INSERT INTO dbo.roommates (name)
    VALUES (N'Alex'), (N'Sam'), (N'Jordan'), (N'Maya');

IF NOT EXISTS (SELECT 1 FROM dbo.chores)
    INSERT INTO dbo.chores (name, frequency_days, [rule])
    VALUES
        (N'Dishes', 1, N'take_turns'),
        (N'Take out the bins', 3, N'take_turns'),
        (N'Clean the bathroom', 7, N'least_recent'),
        (N'Hoover the living room', 7, N'least_recent');
