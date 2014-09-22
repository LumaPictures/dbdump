# dbdump

This command-line tool is a standalone web server that sends a CSV list of changed records in any table (with an auto-updating timestamp column) to clients.

## Running the server

    ./dbdump.py --db-host <mysql_host> --username <mysql_user> --password <mysql_password>


## Examples of command line options

Start the server on port 8888 and connect to database server host 'dbserver' as 'root' without a password:

    ./dbdump.py --db-host dbserver


Start the server on port 8000, use SSL, and require HTTP authentication (as: foo/bar) for clients:

    ./dbdump.py --listen-port 8000 \
                --listen-ssl \
                --listen-username foo \
                --listen-password bar \
                --db-host dbserver \
                --db-username root
                --db-password secret


## Example web queries

Get a list of supported tables in a given database:

    http://localhost:8888/<database_name>/


Get all records modified in table 'foo' since 1/9/2014 1:23:45, only returning columns a, b, and c:

    http://localhost:8888/test/foo/?since=2014-09-01+01:23:45&include_columns=a,b,c


Get all records in a given table, but omit columns x, y, and z:

    http://localhost:8888/test/foo/?exclude_columns=x,y,z
