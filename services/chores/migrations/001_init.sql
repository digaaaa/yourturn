
CREATE TABLE roommates (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE chores (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(200) NOT NULL,
    frequency_days INT NOT NULL,
    [rule] NVARCHAR(100) NOT NULL
);

CREATE TABLE chore_log (
    id INT IDENTITY(1,1) PRIMARY KEY,
    chore_id INT NOT NULL REFERENCES chores(id),
    roommate_id INT NOT NULL REFERENCES roommates(id),
    done_on DATE NOT NULL
);
