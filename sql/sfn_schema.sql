drop table if exists sfn.country cascade;
create table sfn.country (
	country_code	varchar not null primary key,
	country_name	varchar not null,
	continent		varchar null,
	flag_url		varchar
);
create unique index on sfn.country(country_name);

drop table if exists sfn.league;
create table sfn.league (
	league_id		int not null primary key,
	league_name		varchar not null,
	league_type		varchar not null,
	logo_url		varchar,
	country_code	varchar references sfn.country(country_code) on delete cascade
);
--create unique index on sfn.league(league_name, league_type, country_code);

drop table if exists sfn.team;
create table sfn.team (
	team_id			int not null primary key,
	team_name		varchar not null,
	code			varchar,
	country_code	varchar not null references sfn.country(country_code),
	year_founded	int,
	is_national		bool,
	logo_url		varchar
);
create unique index on sfn.team(team_name, country_code);

