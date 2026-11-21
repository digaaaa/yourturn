
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

IF SUSER_ID(N'yourturn_chores_app') IS NULL
    CREATE LOGIN yourturn_chores_app WITH PASSWORD = '$(CHORES_DB_PASSWORD)';
IF SUSER_ID(N'yourturn_supplies_app') IS NULL
    CREATE LOGIN yourturn_supplies_app WITH PASSWORD = '$(SUPPLIES_DB_PASSWORD)';
GO

USE yourturn_chores;
GO
IF USER_ID(N'yourturn_chores_app') IS NULL
    CREATE USER yourturn_chores_app FOR LOGIN yourturn_chores_app;
IF IS_ROLEMEMBER(N'db_owner', N'yourturn_chores_app') = 0
    ALTER ROLE db_owner ADD MEMBER yourturn_chores_app;
GO

USE yourturn_supplies;
GO
IF USER_ID(N'yourturn_supplies_app') IS NULL
    CREATE USER yourturn_supplies_app FOR LOGIN yourturn_supplies_app;
IF IS_ROLEMEMBER(N'db_owner', N'yourturn_supplies_app') = 0
    ALTER ROLE db_owner ADD MEMBER yourturn_supplies_app;
GO

