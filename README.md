# dbdump

Set of command line tools for synchronizing changes made to MySQL tables with auto-updating TIMESTAMP columns.
Doesn't need to track any synchronization state, and assumes timestamps are reliable enough.


## Running the web server (that sends changes)

Use the `dbd_server` command line tool:

    usage: dbdump [-h] [-a IP] [-P PORT] [-u USERNAME] [-p PASSWORD] [-s]
                  [--ssl-private-key FILE_PATH] [--ssl-public-key FILE_PATH] -dh
                  HOST_OR_IP [--db-port PORT] -du USERNAME [-dp PASSWORD] [-d]
                  [--version]

    Web server that sends changed database records to clients. Client can request
    all changed records that occurred since a specific date and time.

    optional arguments:
      -h, --help            show this help message and exit

    Server:
      HTTP server that listens for clients.

      -a IP, --listen-address IP
                            Listener interface address (default: 0.0.0.0)
      -P PORT, --listen-port PORT
                            Listener port (default: 8888)
      -u USERNAME, --listen-username USERNAME
                            Username required for connecting HTTP clients
      -p PASSWORD, --listen-password PASSWORD
                            Password required for connecting HTTP clients
      -s, --listen-ssl      Require SSL encryption
      --ssl-private-key FILE_PATH
                            Private key file in OpenSSL format (default: ssl.key)
      --ssl-public-key FILE_PATH
                            Public key file in OpenSSL format (default: ssl.crt)

    Database:
      MySQL database server where changes are being monitored. All qualified
      tables must have an auto-updating TIMESTAMP column.

      -dh HOST_OR_IP, --db-host HOST_OR_IP
                            Database server host
      --db-port PORT        Database server port (default: 3306)
      -du USERNAME, --db-username USERNAME
                            Database username
      -dp PASSWORD, --db-password PASSWORD
                            Database password

    Misc:
      Miscallaneous options

      -d, --debug           Enable debug mode (shows more detailed logging and
                            auto-restarts web server when script files change)
      --version             Display version and exit

### Examples of command line options

Start the server on port 8888 and connect to database server host 'dbserver' as 'root' without a password:

    ./dbd_server --db-host dbserver


Start the server on port 8000, use SSL, and require HTTP authentication (as: foo/bar) for clients:

    ./dbd_server --listen-port 8000 \
                 --listen-ssl \
                 --listen-username foo \
                 --listen-password bar \
                 --db-host dbserver \
                 --db-username root \
                 --db-password secret \
                 --db-database SOURCE


### Example ad-hoc web queries against `dbd_server`

Get a list of supported tables in a given database:

    http://localhost:8888/<database_name>/


Get all records modified in table 'foo' since 1/9/2014 1:23:45, only returning columns a, b, and c:

    http://localhost:8888/test/foo/?since=2014-09-01+01:23:45&include_columns=a,b,c


Get all records in a given table, but omit columns x, y, and z:

    http://localhost:8888/test/foo/?exclude_columns=x,y,z


## Pulling changes from the server

Use the `dbd_puller` command line tool:

    usage: dbd_puller [-h] -sh HOST_OR_IP [-sP PORT] [-su USERNAME] [-sp PASSWORD]
                      -sd DATABASE -dh HOST_OR_IP [-dP PORT] -du USERNAME
                      [-dp PASSWORD] -dd DATABASE [-d] [--version]

    Pulls changes from a dbd_pusher server

    optional arguments:
      -h, --help            show this help message and exit

    Source dbd_server (that changes are read from):
      -sh HOST_OR_IP, --host HOST_OR_IP
                            dbdump web server
      -sP PORT, --port PORT
                            dbdump web server port (default: 8888)
      -su USERNAME, --username USERNAME
                            dbdump username
      -sp PASSWORD, --password PASSWORD
                            dbdump password
      -sd DATABASE, --database DATABASE
                            Source database name

    Destination MySQL database server (that changes get written to):
      -dh HOST_OR_IP, --db-host HOST_OR_IP
                            Database server host
      -dP PORT, --db-port PORT
                            Database server port (default: 3306)
      -du USERNAME, --db-username USERNAME
                            Database user
      -dp PASSWORD, --db-password PASSWORD
                            Database password
      -dd DATABASE, --db-database DATABASE
                            Destination database name

    Misc:
      Miscallaneous options

      -d, --debug           Enable debug mode
      --version             Display version and exit

### Examples of pulling changes

    ./dbd_puller --host localhost \
                 --port 8888 \
                 --db-host localhost \
                 --db-port 3306 \
                 --db-username root \
                 --db-password secret \
                 --db-database TARGET
