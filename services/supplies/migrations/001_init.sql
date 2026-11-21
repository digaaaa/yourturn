
CREATE TABLE supplies (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(200) NOT NULL,
    [rule] NVARCHAR(100) NOT NULL
);

CREATE TABLE purchases (
    id INT IDENTITY(1,1) PRIMARY KEY,
    supply_id INT NOT NULL REFERENCES supplies(id),
    roommate_id INT NOT NULL,
    price FLOAT NOT NULL,
    bought_on DATE NOT NULL
);
