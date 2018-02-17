# Automates the process of booking slots at the club

import datetime
from time import sleep
import pycurl
import urllib.parse
import io
from bs4 import BeautifulSoup

import credentials

login_url   = credentials.base_url + 'LoginE.aspx'
booking_url = credentials.base_url + 'BookingNewAllE.aspx?ClubCD=KGPA&ClubName=KELAB%20GOLF%20PERKHIDMATAN%20AWAM'
logout_url  = credentials.base_url + 'LogoutE.aspx'

days_ahead     = 8      # slots appear at 22:00 MYT (14:00 GMT) for 8 days ahead
                        # (eg Friday 10pm is when slots appear for next Saturday)
course_list_id = 'lst3' # lst1 = Hills, lst2 = Lakes, lst3= Forest
chosen_slot    = 0      # indicates the list option, zero-indexed. eg. 0 = 7:15, 1 = 7:22, etc
max_attempts   = 2
seconds_between_attempts = 1

def add_state(postfields, raw_html):
    """ strips asp.net tags (__VIEWSTATE, __EVENTVALIDATION etc) from raw HTML
        and adds them to the provided postfields hash
    """
    soup = BeautifulSoup(raw_html, 'html.parser')
    state = { tag['name']: tag['value']
        for tag in soup.select('input[name^=__]')
    }
    postfields.update(state)

def call(url, **kwargs):
    """ uses pycurl to call url, optionally POSTing postfields, if supplied
        returns the response body to our GET or POST request
    """
    buffer = io.BytesIO()
    p.setopt(pycurl.WRITEDATA, buffer)
    p.setopt(pycurl.POST, 0)
    if 'postfields' in kwargs:
        fields = urllib.parse.urlencode(kwargs['postfields'])
        p.setopt(pycurl.POST, 1)
        p.setopt(pycurl.POSTFIELDS, fields)
    p.setopt(pycurl.URL, url)
    p.perform()
    return buffer.getvalue()

p = pycurl.Curl()
p.setopt(pycurl.FOLLOWLOCATION, 1)
p.setopt(pycurl.COOKIEFILE, './cookie.txt')
p.setopt(pycurl.COOKIEJAR, './cookie.txt')

# Get login page
print("logging in...", end='')
raw_html = call(login_url)
# Post login info
postfields = {
    'TextBox1': credentials.username,
    'TextBox2': credentials.password,
    'btnLogin': 'Login',
    }
add_state(postfields, raw_html)
call(login_url, postfields=postfields)
print("complete")

# Get booking page
booking_date = datetime.date.today() + datetime.timedelta(days=days_ahead)
date_string  = booking_date.strftime("%Y/%m/%d")
print("finding booking slots on {}...".format(date_string))
raw_html = call(booking_url)

# Post for newest slots
postfields = {
    'ddlClub' : '8',
    'ddldate' : date_string,
    'ddlH1'   : '7',
    'ddlM1'   : '00',
    'ddlAMPM1': 'AM',
    'ddlH2'   : '8',
    'ddlM2'   : '00',
    'ddlAMPM2': 'AM',
}
add_state(postfields, raw_html)

attempts = 0
tag_slot_option = None
while True:
    attempts += 1
    print(" attempt {}...".format(attempts), end='')
    raw_html = call(booking_url, postfields=postfields)
    soup = BeautifulSoup(raw_html, 'html.parser')
    if soup.find(id=course_list_id) is not None:
        tag_slot_option = soup.find(id=course_list_id).find_all("option")[chosen_slot]
        print(" found!")
        break
    if attempts > max_attempts:
        print(" not found, stopping")
        break
    print(" not found, retrying")
    sleep(seconds_between_attempts)

if tag_slot_option is not None:
    print(" found slot {}".format(tag_slot_option.string))

    # Post to book desired slots
    print("Attempting to book...", end='')
    postfields.update({
        course_list_id: tag_slot_option['value'],
        'butChange': 'Confirm and Booking',
    })
    add_state(postfields, raw_html)
    raw_html = call(booking_url, postfields=postfields)
    soup     = BeautifulSoup(raw_html, 'html.parser')
    message  = soup.find(id="lblMsg").string

    if message is None:
        import re
        message = re.search(r'Your booking is confirmed. The reference number is \w+', raw_html.decode('utf-8'), re.M).group()

    print(" booking submitted\nServer's response: \"{}\"\n\n".format(message))

else:
    print("\nfailed to load slots to book\n")

# Logout
call(logout_url)
p.close()
