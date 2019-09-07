from . import join_abs
import json
from xml.dom.minidom import parseString
import socket
import sqlite3
import glob


class Aggregation:
    def __init__(self, db_filename, domain, output_dir):
        self.dbfile = db_filename
        self.domain = domain
        self.output_dir = output_dir

    def dump_to_file(
            self,
            dump_ips=True,
            dump_hostnames=True,
            dump_headers=False):
        dbconn = sqlite3.connect(self.dbfile)
        try:
            dbcurs = dbconn.cursor()

            ips = dbcurs.execute(f"""SELECT DISTINCT ip
                                    FROM data
                                    WHERE domain='{self.domain.replace('.', '_')}'
                                    AND ip IS NOT NULL"""
                                 ).fetchall()
            hostnames = dbcurs.execute(f"""SELECT DISTINCT hostname
                                            FROM data
                                            WHERE domain='{self.domain.replace('.', '_')}'
                                            AND hostname IS NOT NULL"""
                                       ).fetchall()

            """
                Header options require there to have been a scan otherwise there will be no output but that should be expected.
                Might change db to a dataframe later... possible
            """
            headers = dbcurs.execute(
                f"""SELECT DISTINCT ip, hostname, http_headers, https_headers
                                        FROM data
                                        WHERE domain='{self.domain.replace('.', '_')}'
                                        AND (http_headers IS NOT NULL
                                        AND https_headers IS NOT NULL)""").fetchall()

            if dump_ips:
                with open(join_abs(self.output_dir, 'aggregated', 'aggregated_ips.txt'), 'w') as f:
                    f.writelines("\n".join(list(ip[0] for ip in ips)))

            if dump_hostnames:
                with open(join_abs(self.output_dir, 'aggregated', 'aggregated_hostnames.txt'), 'w') as f:
                    f.writelines(
                        "\n".join(
                            list(
                                f"{host[0]}" for host in hostnames)))

                with open(join_abs(self.output_dir, 'aggregated', 'aggregated_protocol_hostnames.txt'), 'w') as f:
                    f.writelines(
                        "\n".join(
                            list(
                                f"https://{host[0]}\nhttp://{host[0]}" for host in hostnames)))

            if dump_headers:
                KEYS = ["Ip", "Hostname", "Http", "Https"]
                for row in headers:
                    r = dict(zip(KEYS, row))
                    with open(join_abs(self.output_dir, "headers", f"{r['Hostname']}_headers.txt"), 'w') as f:
                        f.write(json.dumps(r, indent=2))
        except Exception as e:
            print("Failed to write to files in aggregated directory, exiting...")
            print(e)
            return
        finally:
            dbconn.close()

    def _build_db(ips, cursor):
        cursor.execute('BEGIN TRANSACTION')
        domain = self.domain.replace(".", "_")
        try:
            for host, ip in ips:
                cursor.execute("""INSERT INTO data
                                    (ip, hostname, http_headers, https_headers, domain)
                                    VALUES (?,?, NULL, NULL, ?);""",
                               (ip, host, domain))
        except BaseException:
            print(f"Issue with the following data: {ip} {host} {domain}")

        cursor.execute('COMMIT')

    def _read_file(filename):
        with open(join_abs(self.OUTPUT_DIR, filename), 'r') as f:
            chunks = []
            chunk_size = 10000
            for line in f:
                chunks += [line]
                if len(chunks) >= chunk_size:
                    yield chunks
                    chunks = []
            yield chunks

    def aggregate(self, verify=None, output_files=[], output_folders=[]):
        try:

            dbconn = sqlite3.connect(self.dbfile)
            dbcurs = dbconn.cursor()
            # Enable foreign key support
            dbcurs.execute("PRAGMA foreign_keys=1")
            # Simple database that contains list of domains to run against
            dbcurs.execute("""
                            CREATE TABLE IF NOT EXISTS domains (
                                domain VARCHAR PRIMARY KEY,
                                UNIQUE(domain)
                            )
                            """)
            # Setup database to keep all data from all targets. This allows us
            # to use a single model for hosting with Django
            dbcurs.execute("""
                            CREATE TABLE IF NOT EXISTS data (
                                domainid INTEGER PRIMARY KEY,
                                ip VARCHAR,
                                hostname VARCHAR,
                                http_headers TEXT,
                                https_headers TEXT,
                                domain VARCHAR,
                                FOREIGN KEY(domain) REFERENCES domains(domain),
                                UNIQUE(ip, hostname)
                            )
                            """)
            # Quickly create entry in domains table.
            dbcurs.execute(
                f"INSERT OR IGNORE INTO domains(domain) VALUES ('{self.domain.replace('.', '_')}')")
            dbconn.commit()

            all_files = []
            for name in output_files:
                if isfile(join_abs(self.output_dir, name)):
                    all_files += [join_abs(self.output_dir, name)]
                elif isfile(name):
                    all_files += [name]
                else:
                    print(
                        f"[!] File {name} does not exist, verify scan results")

            for folder in output_folders:
                for root, dirs, files in walk(
                        join_abs(self.output_dir, folder)):
                    for f in files:
                        if isfile(join_abs(root, f)):
                            all_files += [join_abs(root, f)]

            self._print(f"Parsing all files {all_files}")
            all_ips = []
            for filename in all_files:
                print(f"[*] Parsing file: {filename}")
                all_ips += self._reverse_ip_lookup(filename)
                # for data in read_file(join_abs(filename)):
                #     all_ips += self._reverse_ip_lookup(data)
            build_db(all_ips, dbcurs)
            dbconn.commit()
        finally:
            dbconn.close()

    def _reverse_ip_lookup(self, filename):
        print("Extracting ips and hostnames from text")
        ip_reg = re.compile(
            r"(?:(?:1\d\d|2[0-5][0-5]|2[0-4]\d|0?[1-9]\d|0?0?\d)\.){3}(?:1\d\d|2[0-5][0-5]|2[0-4]\d|0?[1-9]\d|0?0?\d)")
        #hostname_reg = re.compile(r"([A-Za-z0-9\-]*\.?)*\." + self.domain)
        hostname_reg = re.compile(
            r"([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])(\.([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9]))*?\." +
            self.domain)
        results = []
        with open(filename, "r") as f:
            for line in tqdm(f.readlines()):
                host = hostname_reg.match(line)
                if host:
                    host = host.group()
                ip = ip_reg.match(line)
                if ip:
                    ip = ip.group()
                try:
                    if host is not None and ip is None:
                        ip = socket.gethostbyname(host)
                    if ip is not None and host is None:
                        host = socket.gethostbyaddr(ip)
                except BaseException:
                    pass
                if host or ip:
                    results += [(host, ip)]

        return results

    @staticmethod
    def _get_headers(ip):
        http = None
        https = None
        # May add option later to set UserAgent
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/54.0"
        }
        try:
            http = requests.get(
                f"http://{ip}",
                headers=headers,
                timeout=1,
                verify=False).headers
            http = str(http)
        except Exception as er:
            logger.exception(f"Could not retrieve http header for ip: {ip}")
            pass
        try:
            https = requests.get(
                f"https://{ip}",
                headers=headers,
                timeout=1,
                verify=False).headers
            https = str(https)
        except BaseException:
            logger.exception(f"Could not retrieve https header for ip: {ip}")
            pass
        return ip, (http, https)

    def headers(self):
        dbconn = sqlite3.connect(self.dbfile)
        dbcurs = dbconn.cursor()

        print("[*] Grabbing headers from ips and hostnames")
        ips = dbcurs.execute(f"""SELECT ip
                                    FROM data
                                    WHERE ip IS NOT NULL
                                    AND domain='{self.domain.replace('.','_')}'"""
                             ).fetchall()
        ips = [item[0] for item in ips]
        # Threading is done against the staticmethod. Feel free to change the max_workers if your system allows.
        # May add option to specify threaded workers.
        with ThreadPoolExecutor(max_workers=40) as pool:
            ip_headers = dict(tqdm(pool.map(Robot.grab_header,
                                            ips),
                                   total=len(ips)))
        dbcurs.execute('BEGIN TRANSACTION')
        domain_rep = self.domain.replace(".", "_")
        for ip, (http, https) in ip_headers.items():
            dbcurs.execute(f"""UPDATE data
                                SET http_headers=?, https_headers=?
                                WHERE ip = ?
                                AND domain= ?
                                LIMIT 1;""",
                           (http, https, ip, domain_rep))
        dbcurs.execute("COMMIT")

        hostnames = dbcurs.execute(f"""SELECT ip
                                    FROM data
                                    WHERE ip IS NOT NULL
                                    AND domain='{self.domain.replace('.','_')}'"""
                                   ).fetchall()
        hostnames = [item[0] for item in hostnames]
        with ThreadPoolExecutor(max_workers=40) as pool:
            hostname_headers = dict(tqdm(pool.map(Robot.grab_header,
                                                  hostnames),
                                         total=len(hostnames)))
        dbcurs.execute('BEGIN TRANSACTION')
        domain_rep = self.domain.replace(".", "_")
        for hostname, (http, https) in hostname_headers.items():
            dbcurs.execute(f"""UPDATE data
                                SET http_headers=?, https_headers=?
                                WHERE hostname = ?
                                AND domain= ?
                                LIMIT 1;""",
                           (http, https, hostname, domain_rep))
        dbcurs.execute("COMMIT")

        dbconn.close()

    def _gen_output(self):
        if not exists(self.dbfile):
            self._print("No database file found. Exiting")
            return

        dbconn = sqlite3.connect(self.dbfile)
        dbcurs = dbconn.cursor()

        db_headers = dbcurs.execute(f"""SELECT *
                                        FROM data
                                        WHERE domain='{self.domain.replace('.','_')}'
                                        AND (http_headers IS NOT NULL OR https_headers IS NOT NULL)"""
                                    ).fetchall()
        db_ips = dbcurs.execute(f"""SELECT DISTINCT ip, hostname
                                    FROM data
                                    WHERE domain='{self.domain.replace('.', '_')}'"""
                                ).fetchall()

        """
        (IP, HOSTNAME, HTTP, HTTPS)
        """
        file_index = {}
        """
            Need to be smarter about this:

            Multiple different sql queries
                1. Grabs all those with headers:
                    most likely that if they have headers they have a screenshot
                    glob can run and take it's time.
                2. Grab all unique ips
                2a. Grab all unique hostnames

                3. Update json with all documents
        """
        for _, ip, hostname, http, https, domainname in db_headers:
            ip_screenshots = glob.glob("**/*{}*".format(ip), recursive=True)
            hostname_screeshots = glob.glob(
                "**/*{}*".format(hostname), recursive=True)

            image_files = []
            for _file in ip_screenshots:
                image_files += [join_abs(getcwd(), _file)]
            for _file in hostname_screeshots:
                image_files += [join_abs(getcwd(), _file)]
            file_index[ip] = {
                "hostnames": [hostname],
                "http_header": http,
                "https_header": https,
                "images": image_files
            }

        for ip, hostname in db_ips:
            if ip not in file_index:
                file_index[ip] = {
                    "hostnames": [hostname],
                    "http_header": "",
                    "https_header": "",
                    "images": []
                }
            elif hostname not in file_index[ip]['hostnames']:
                file_index[ip]['hostnames'] += [hostname]
        return file_index
