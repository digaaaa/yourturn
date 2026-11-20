
-- Create the Chores database if it doesn't already exist.
IF DB_ID('yourturn_chores') IS NULL
BEGIN
    CREATE DATABASE yourturn_chores;
END;
GO

-- Create the Supplies database if it doesn't already exist.
IF DB_ID('yourturn_supplies') IS NULL
BEGIN
    CREATE DATABASE yourturn_supplies;
END;
GO

