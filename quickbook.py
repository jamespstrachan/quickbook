# Automates the process of booking slots at the club

import os, datetime, io, pycurl, urllib.parse
from time import sleep
from bs4 import BeautifulSoup

days_ahead     = 8      # slots appear at 22:00 MYT (14:00 GMT) for 8 days ahead
                        # (eg Friday 10pm is when slots appear for next Saturday)
course_list_ids = ['lst3', 'lst2']
                        # in descending order of preference
                        # lst1 = Hills, lst2 = Lakes, lst3 = Forest
chosen_slot    = 0      # indicates the list option, zero-indexed. eg. 0 = 7:15, 1 = 7:22, etc
max_attempts   = 30
seconds_between_attempts = 0

def main():
    """ Attempts to book first available slot as soon as possible by polling
    """
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    check_credentials()
    import credentials
    login_url   = credentials.base_url + 'LoginE.aspx'
    booking_url = credentials.base_url + 'BookingNewAllE.aspx?ClubCD=KGPA&ClubName=KELAB%20GOLF%20PERKHIDMATAN%20AWAM'
    logout_url  = credentials.base_url + 'LogoutE.aspx'

    cookie_file_path = './cookie.txt'
    if os.path.isfile(cookie_file_path) == True:
        os.remove(cookie_file_path)
    p = pycurl.Curl()
    p.setopt(pycurl.FOLLOWLOCATION, 1)
    p.setopt(pycurl.COOKIEFILE, cookie_file_path)
    p.setopt(pycurl.COOKIEJAR, cookie_file_path)

    print(datetime.datetime.now().strftime('%c'))
    # Get login page
    log("logging in...", end='')
    raw_html = call(p, login_url)
    # Post login info
    postfields = {
        'TextBox1': credentials.username,
        'TextBox2': credentials.password,
        'btnLogin': 'Login',
        }
    add_state(postfields, raw_html)
    call(p, login_url, postfields=postfields)
    log("complete")

    log("delaying till start of next minute", end="\n")
    sleep(60 - datetime.datetime.now().second)

    booking_date = datetime.date.today() + datetime.timedelta(days=days_ahead)
    date_string  = booking_date.strftime("%Y/%m/%d")
    default_postfields = {
        'ddlClub' : '8',
        'ddldate' : date_string,
        'ddlH1'   : '7',
        'ddlM1'   : '00',
        'ddlAMPM1': 'AM',
        'ddlH2'   : '8',
        'ddlM2'   : '00',
        'ddlAMPM2': 'AM',
    }
    log("finding booking slots on {}".format(date_string), end="\n")
    attempts = 0
    tag_slot_option = None
    while True:
        attempts += 1
        log(" attempt {}...".format(attempts), end='')

        # List available booking days
        raw_html = call(p, booking_url)

        postfields = default_postfields
        add_state(postfields, raw_html)

        # List available booking slots on chosen day
        raw_html = call(p, booking_url, postfields=postfields)
        soup = BeautifulSoup(raw_html, 'html.parser')
        for course_list_id in course_list_ids:
            if soup.find(id=course_list_id) is not None:
                tag_slot_option = soup.find(id=course_list_id).find_all("option")[chosen_slot]
                if tag_slot_option is not None:
                    break
        if tag_slot_option is not None:
            log(" found!")
            break
        if attempts >= max_attempts:
            log(" not found, stopping")
            break
        log(" not found, retrying")
        sleep(seconds_between_attempts)

    if tag_slot_option is not None:
        log(" found slot {}".format(tag_slot_option.string))

        # Post to book desired slots
        log("Attempting to book...", end='')
        postfields.update({
            course_list_id: tag_slot_option['value'],
            'butChange': 'Confirm and Booking',
        })
        add_state(postfields, raw_html)
        raw_html = call(p, booking_url, postfields=postfields)
        soup     = BeautifulSoup(raw_html, 'html.parser')
        message  = soup.find(id="lblMsg").string

        if message is None:
            import re
            message = re.search(r'Your booking is confirmed. The reference number is \w+', raw_html.decode('utf-8'), re.M).group()

        log(" booking submitted")
        log("Server's response: \"{}\"\n\n".format(message), end='')

    else:
        log("\nfailed to load slots to book\n")

    # Logout
    call(p, logout_url)
    p.close()
    os.remove(cookie_file_path)

def check_credentials():
    """ Loads credentials if present or requests from user
    """
    credentials_path = "credentials.py"
    if os.path.isfile(credentials_path) == False:
        log("Setup required, no credentials found")
        username = input("  username:")
        password = input("  password:")
        base_url = input("  base url:")
        fh = open(credentials_path, "w")
        lines = [
            "# application credentials",
            "username = '{}'".format(username),
            "password = '{}'".format(password),
            "base_url = '{}'".format(base_url),
            ]
        fh.write("\n".join(lines))
        fh.close()
        log("Setup complete\n")

def add_state(postfields, raw_html):
    """ strips asp.net tags (__VIEWSTATE, __EVENTVALIDATION etc) from raw HTML
        and adds them to the provided postfields hash
    """
    soup = BeautifulSoup(raw_html, 'html.parser')
    state = { tag['name']: tag['value']
        for tag in soup.select('input[name^=__]')
    }
    postfields.update(state)

def call(conn, url, **kwargs):
    """ uses pycurl to call url, optionally POSTing postfields, if supplied
        returns the response body to our GET or POST request
    """
    buffer = io.BytesIO()
    fields = ''
    conn.setopt(pycurl.WRITEDATA, buffer)
    conn.setopt(pycurl.POST, 0)
    if 'postfields' in kwargs:
        fields = urllib.parse.urlencode(kwargs['postfields'])
        conn.setopt(pycurl.POST, 1)
        conn.setopt(pycurl.POSTFIELDS, fields)
    conn.setopt(pycurl.URL, url)
    conn.perform()
    response_body = buffer.getvalue()
    fh = open("html_log.txt", "a")
    fh.write(str(datetime.datetime.now())+"\n")
    fh.write("{} ? {}\n".format(url, fields))
    fh.write(str(response_body)+"\n\n")
    fh.close()
    if str(response_body).find("Invalid postback or callback argument") > -1:
        log(" !Error response from server! ", end='')
    return response_body

def log(msg, **kwargs):
    """ controls output to screen, adding timing details where relevant
    """
    timestring = "\033[90m{}\033[0m  ".format(datetime.datetime.now().strftime('%H:%M:%S.%f'))
    preamble = timestring if 'end' in kwargs else ''
    print(preamble+msg, **kwargs)

if __name__ == "__main__":
    main()
