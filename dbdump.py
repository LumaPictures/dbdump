#!/usr/bin/env python
"""
Standalone web server that outputs changes that occurred on a table since a specific date.


Example usage:

    ./dbdump.py --host devdb-vip --username internal --password xxx


You can then get the CSV output of all changes by browsing to:

    http://localhost:8888/lumaweb/job_app?since=2014-09-01+01:23:45&exclude_columns=links,files,message


"""
import sys
import argparse
import socket
import logging
import json
import datetime
import traceback
import functools

from flask import Flask, abort, render_template, request, Response
import MySQLdb, _mysql_exceptions

__version__ = '1.0.0'

app = application = Flask(__name__.split('.')[0])
logger = logging.getLogger(__name__)
arguments = {}  # Parsed arguments


def requires_auth(f):
    """
    Authentication decorator used for Flask endpoints.

    If you're mounting this script as a WSGI endpoint and you're using Apache, 
    ensure WSGIPassAuthorization=On in Apache's config, or auth will always fail.
    """
    @functools.wraps(f)
    def requires_auth_decorated(*args, **kwargs):
        expected_username = arguments.get('listen_username')
        expected_password = arguments.get('listen_password')
        
        if expected_username and expected_password:
            # Authentication is required (since user and pass configured)
            creds = request.authorization
            if (not creds) or (not (creds.username == expected_username and creds.password == expected_password)):
                # Authentication failed or credentials not provided
                logger.warn('Login failed for %s when accessing %s' % (request.remote_addr, request.url))
                return make_text_response('Authentication failed\n', 401)

        # Pass through
        return f(*args, **kwargs)

    return requires_auth_decorated


def requires_acceptance_of(mime_types):
    """
    Accept mime-type decorator used for Flask endpoints.
    """
    def inner_fn(f):
        def requires_acceptance_of_decorated(*args, **kwargs):
            best_match = request.accept_mimetypes.best_match(mime_types)
            if best_match is None:
                # 506 Not Acceptable
                return make_text_response('Only acceptable MIME types are: %s\n' % (', '.join(mime_types)), 506)
            else:
                return f(*args, **kwargs)
        return functools.wraps(f)(requires_acceptance_of_decorated)
    return inner_fn


@app.errorhandler(Exception)
def errorException(exc):
    """
    Catch-all exception handler
    """
    trace = traceback.format_exc()
    logger.error(exc)
    logger.error(trace)
    return json.dumps({
            'exception': exc.__class__.__name__,
            'message': str(exc),
            'traceback_lines': trace.splitlines(),
            'traceback': trace
        }), 500, {
        'Content-Type': 'application/json'
    }    


@app.route('/favicon.ico')
@app.route('/index.html')
def favicon():
    """
    Files that the browser may automatically ask for.
    """
    abort(404)


@app.route('/<string:database>')
@requires_auth
@requires_acceptance_of(['text/csv'])
def tables(database):
    """
    CSV list of all supported tables.
    """
    conn = get_db_connection()
    try:
        supported_tables = get_autoupdate_timestamp_columns(conn, database).keys()
        return make_csv_response(map(lambda r: (r,), supported_tables), ['table'])

    finally:
        conn.close()


@app.route('/<string:database>/<string:table>')
@requires_auth
@requires_acceptance_of(['text/csv'])
def updated_rows(database, table):
    """
    CSV list of all rows modified since :since: (in the query args) in the given table.
    """
    conn = get_db_connection()
    try:
        timestamp_columns = get_autoupdate_timestamp_columns(conn, database)

        # There can only be one auto-updating timestamp column in a table
        ts_column = timestamp_columns.get(table)
        if ts_column is None:
            return make_text_response('Table "%s" does not have an auto-updated timestamp column\n', 404)

        # Since filter
        since = get_datetime_arg('since')

        # Column projection
        columns = get_projection(conn, database, table, 
                                 include_columns=get_list_arg('include_columns'), 
                                 exclude_columns=get_list_arg('exclude_columns'))
        if len(columns) == 0:
            return make_text_response('No matching columns found\n', 400)

        # Build query to fetch updated rows
        cursor = conn.cursor()
        quote = MySQLdb.escape_string

        # Filter
        where_expr = []
        where_args = []
        if since is not None:
            where_expr.append('`%s` > %%s' % quote(ts_column))
            where_args.append(since)
        if len(where_expr):
            where_stmt = ' where ' + ' and '.join(where_expr)
        else:
            where_stmt = ''

        query = "select `%(projection)s` from `%(database)s`.`%(table)s` %(where_stmt)s order by `%(ts_column)s`" % dict(
                    projection='`, `'.join(map(quote, columns)), 
                    database=quote(database), 
                    table=quote(table), 
                    where_stmt=where_stmt, 
                    ts_column=quote(ts_column))

        # Execute query
        logger.debug(query % tuple(where_args))
        cursor.execute(query, where_args)
        return make_csv_response(cursor.fetchall(), columns)

    finally:
        conn.close()


def make_csv_response(row_iter, column_names):
    """
    Helper that constructs a streaming CSV response to send back to the client.
    """
    return Response(CSVGenerator()(row_iter, column_names), 
                    headers={'Content-Type': 'text/csv'})


def make_text_response(message, status_code):
    """
    Helper that constructs a text response to send back to the client.
    """
    return Response(message, status_code, 
                    headers={'Content-Type': 'text/plain'})


class CSVGenerator(object):
    def __init__(self,
                 sep_char=',', 
                 quote_char='"', 
                 escape_char='\\',
                 newline_char='\n'):
        self.sep_char = sep_char
        self.quote_char = quote_char
        self.escape_char = escape_char
        self.newline_char = newline_char

    def __call__(self, row_iterator, column_names):
        """
        Generator streams rows to the client as they are fetched.
        This prevents server-side buffering of results, which could eat alot of memory.
        """
        assert len(column_names) > 0

        emit_header = True
        for row in row_iterator:
            assert len(row) == len(column_names), '%d != %d' % (len(row), len(column_names))

            # Emit header as first row
            if emit_header:
                yield self._encode_row(column_names, column_names)
                emit_header = False

            yield self._encode_row(row, column_names)

    def _encode_row(self, row, column_names):
        """
        Encodes a row in CSV format.
        Used instead of csvwriter since it's quicker.
        """
        encoded_row = []
        for column_idx, column in enumerate(column_names):
            encoded_row.append(self._encode_column(row[column_idx]))

        return ','.join(encoded_row) + self.newline_char

    def _encode_column(self, data):
        """
        Encodes and quotes a single CSV column.
        """
        if data is None:
            return ''
        else:
            return self.quote_char + \
                str(data).replace(self.quote_char, self.escape_char + self.quote_char) + \
                self.quote_char


def get_projection(conn, database, table, include_columns=None, exclude_columns=None):
    """
    Determine projection for a table based on intersection of include_columns and 
    available columns (defined in schema) with the exception of exclude_columns.
    """
    cursor = conn.cursor()
    cursor.execute("""
        select column_name
        from information_schema.columns
        where table_schema = %s and table_name = %s
        order by ordinal_position
        """, (database, table))

    def column_matches(column_name):
        if len(include_columns):
            if column_name not in include_columns:
                return False
        if len(exclude_columns):
            if column_name in exclude_columns:
                return False
        return True

    return [r[0] for r in cursor.fetchall() if column_matches(r[0])]


def get_autoupdate_timestamp_columns(conn, database):
    """
    Returns a dict of {table_name: timestamped_column_name} for only the
    tables that have auto-updated timestamps.
    """
    cursor = conn.cursor()
    cursor.execute("""
        select
            table_name,
            column_name
        from information_schema.columns
        where
            table_schema = %s and
            data_type = 'timestamp' and
            extra = 'on update CURRENT_TIMESTAMP'
        order by table_name
        """, (database,))

    # There shouldn't be any duplicate entries for tables in this list, since
    # MySQL specifies that there can only be one auto-updated timestamp column.
    return dict(map(lambda r: (r[0], r[1]), cursor.fetchall()))


def get_datetime_arg(key, args=None):
    """
    Get a query argument containing a date and time.
    Returns None if nothing found.
    Raises a ValueError on parse failure.
    """
    if args is None:
        args = request.args

    if key in request.args:
        try:
            return datetime.datetime.strptime(request.args['since'], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                return datetime.datetime.strptime(request.args['since'], '%Y-%m-%d')
            except ValueError:
                raise ValueError('"%s" argument is not in the correct format of YYYY-MM-DD HH:MM:SS' % key)


def get_list_arg(key, args=None):
    """
    Get a query argument containing a comma-separated list of values.
    Returns an empty list if nothing found.
    """
    if args is None:
        args = request.args

    if key in request.args:
        value = request.args[key].split(',')
    else:
        value = []

    return value


def get_db_connection():
    """
    Gets a connection to the database server.
    """
    return MySQLdb.connect(host=arguments['db_host'], 
                           port=arguments['db_port'],
                           user=arguments['db_username'], 
                           passwd=arguments['db_password'],
                           db='information_schema')


def main():
    """
    Run as a standalone web server from the command line.
    Don't do this in production. Use your web server to mount this script as a WSGI endpoint instead.
    """
    debug = arguments['debug']

    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO,
                        format='[%(levelname)s] %(name)s: %(message)s')

    logger.debug('Arguments: %s' % json.dumps(arguments))

    # Test database connection
    try:
        logger.debug('Testing database connection...')
        conn = get_db_connection()
        conn.close()
    except _mysql_exceptions.OperationalError, ex:
        code, message = ex.args
        logger.error('MySQL error %s: %s' % (code, message))
        return 1

    # Start web server
    try:
        if debug:
            app.debug = True
            app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Don't cache files

        use_ssl = arguments['listen_ssl']
        if use_ssl:
            try:
                from OpenSSL import SSL
                ssl_context = SSL.Context(SSL.SSLv23_METHOD)
                ssl_context.use_privatekey_file(arguments['ssl_private_key'])
                ssl_context.use_publickey_file(arguments['ssl_public_key'])
            except ImportError:
                logger.error('You enabled SSL mode, but the OpenSSL module not installed! '
                             'Please "pip install pyopenssl" to satisfy this dependency.')
                return 1
        else:
            ssl_context = None

        logger.info('Starting server on %s://%s:%d' % (
                    ('https' if use_ssl else 'http'), arguments['listen_address'], arguments['listen_port']))

        app.run(host=arguments['listen_address'], 
                port=arguments['listen_port'],
                ssl_context=ssl_context)
        return 0

    except socket.error, ex:
        print 'Socket error: %s' % ex
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Standalone web server that outputs changes that occurred on a table since a specific date')

    # HTTP server
    parser.add_argument('--listen-address', default='0.0.0.0', 
                        help='HTTP server listen address')
    parser.add_argument('--listen-port', type=int, default=8888, 
                        help='HTTP server port')
    parser.add_argument('--listen-username',
                        help='HTTP basic auth username (required for all connecting clients)')
    parser.add_argument('--listen-password',
                        help='HTTP basic auth password (required for all connecting clients)')

    # SSL mode
    parser.add_argument('--listen-ssl', action='store_true',
                        help='Enable SSL mode on HTTP listener (requires OpenSSL module)')
    parser.add_argument('--ssl-private-key', default='ssl.key',
                        help='OpenSSL private key file (*.key)')
    parser.add_argument('--ssl-public-key', default='ssl.crt',
                        help='OpenSSL public key file (*.crt)')

    # Database client
    parser.add_argument('--db-host', required=True, 
                        help='Database server host')
    parser.add_argument('--db-port', type=int, default=3306,
                        help='Database server port')
    parser.add_argument('--db-username', default='root',
                        help='Database user')
    parser.add_argument('--db-password', default='',
                        help='Database password')

    # Misc options
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode')
    parser.add_argument('--version', action='version',
                        version='%%(prog)s (version %s)' % __version__,
                        help='Display version and exit')

    arguments = vars(parser.parse_args())
    sys.exit(main())
