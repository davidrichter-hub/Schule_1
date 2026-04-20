drop table resourcen;
CREATE TABLE Resourcen (
    id serial PRIMARY KEY,
    ram_total_gb TEXT,
   	ram_used_gb TEXT,
    ram_percent text,
    disk_total_gb TEXT,
    disk_used_gb TEXT,
	disk_percent TEXT,
	cpu_name TEXT,
	cpu_percent TEXT,
	cpu_cores TEXT,
	cpu_threads TEXT,
	creDate timestamp default current_timestamp
);


alter table daten add column creDate timestamp default current_timestamp;

select *
from Resourcen