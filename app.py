from flask import Flask, redirect, request, url_for, render_template
import ConfigParser
import os
# from os import path
# from pathlib import Path
import json
import subprocess
import re
import random
from decimal import Decimal
from validate_email import validate_email

configParser = ConfigParser.RawConfigParser()
configFilePath = './config.ini'
configParser.read(configFilePath)
app = Flask(__name__)

if 'TIGO_HOME' in os.environ:
    TIGO_HOME = os.environ['TIGO_HOME']
else:
    TIGO_HOME = "/home/tigoctm/"

def ptyRender(kwargs=None):
    if kwargs is None:
        kwargs = {}
    kwargs['prices'] = {'BTC': 0, 'DASH': 0, 'guld': 50}
    search = "P"
    try:
        grep = subprocess.check_output([
            'grep',
            '-rI',
            search, '%sledger/prices/' % TIGO_HOME
        ])
        if (grep and len(grep) > 1):
            kwargs['prices'] = {
                'BTC': Decimal(re.search('BTC \$[ 0-9.]*', grep).group(0).replace('BTC', '').replace('$', '').replace(' ', '')),
                'DASH': Decimal(re.search('DASH \$[ 0-9.]*', grep).group(0).replace('DASH', '').replace('$', '').replace(' ', ''))
                'guld': Decimal(re.search('guld \$[ 0-9.]*', grep).group(0).replace('DASH', '').replace('$', '').replace(' ', ''))
            }
            kwargs['prices']['BTC'] = kwargs['prices']['BTC'].quantize(Decimal(0.001))
            kwargs['prices']['DASH'] = kwargs['prices']['DASH'].quantize(Decimal(0.001))
            kwargs['prices']['guld'] = kwargs['prices']['guld'].quantize(Decimal(0.001))
    except Exception as e:
        print(e)
    kwargs['prices']['BTC'] = str(kwargs['prices']['BTC'])
    kwargs['prices']['DASH'] = str(kwargs['prices']['DASH'])
    kwargs['prices']['guld'] = str(kwargs['prices']['guld'])
    return json.dumps(kwargs)

def getAssets(commodity, address):
    ledgerBals = subprocess.check_output([
        '/usr/bin/ledger',
        '-f',
        '%sledger/%s/%s/included.dat' % (TIGO_HOME, commodity, address), 'bal'
    ])
    if (ledgerBals):
        ledgerBals = ledgerBals.split('\n')
    for line in ledgerBals:
        if re.search(' (Assets|Payable):{0,1}\w*$', line):
            return line.replace('Assets', '').replace(commodity, '').replace(' ', '').replace('Payable', '')
    return 0

def getAddresses(username):
    search = ';ptyglass:%s' % username
    grep = "";
    try:
        grep = subprocess.check_output([
            'grep',
            '-r',
            search, '%sledger/' % TIGO_HOME
        ])
    except subprocess.CalledProcessError as cpe:
        print(cpe)
    if (grep):
        grep = grep.split('\n')
    addys = {}
    for line in grep:
        if len(line) == 0:
            break
        line = line.replace('%sledger/' % TIGO_HOME, '').split('/')
        assets = Decimal(getAssets(line[0], line[1]))
        if (line[0] in addys):
            addys[line[0]][line[1]] = assets
            addys[line[0]]['sub-total'] = addys[line[0]]['sub-total'] + assets
        else:
            addys[line[0]] = {line[1]: assets, 'sub-total': assets}
    for c in addys:
        for a in addys[c]:
            addys[c][a] = str(addys[c][a])
    return addys

def mkdirp(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == os.errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

@app.route('/api/register',  methods = ['POST'])
def register():
    """
    Register a new user with a public name and private contact info.
    Generate a payment address, if crypto currency is specified.
    Finally redirect to /api/id to return the user's info.
    Use POST form data for this method.

    :param username: The user's public name.
    :param commodity: Commodity to pay in.
    :param email: The user's email address for tickets and important information.
    :param fullname: The user's private, used for matching tickets at the door.
    """
    # TODO check if user exists and do not overwrite
    mkdirp('%speople/%s/' % (TIGO_HOME, username))
    username = request.form['username']
    commodity = request.form['commodity']
    # TODO encrypt and store contact info, then email
    email = request.form['email']
    fullname = request.form['fullname']
    if commodity in ['BTC', 'DASH', 'guld']:
        return genaddress(commodity, username)
    else:
        return redirect(url_for('identity', username=username))

@app.route('/api/id/<username>')
def identity(username=None):
    """
    Show all info a user would need to make a deposit. i.e. price and addresses
    Response is json formatted dict.
    Use the path to specify the parameters for this method.

    :param username: The user's public name.
    """
    if (username):
        depAddys = getAddresses(username)
        return ptyRender({'username':username, 'depositAddresses':depAddys})
    return ptyRender()

@app.route('/api/address/generate/<commodity>/<username>')
def genaddress(commodity, username):
    """
    Generate a payment address for the given user and commodity.
    Use the path to specify the parameters for this method.

    :param username: The user's public name.
    :param commodity: Commodity to pay in.
    """
    try:
        assert commodity in ['BTC', 'DASH', 'guld']
    except AssertionError as ae:
        return json.dumps({'error': True, 'message': 'invalid commodity'})
    addys = getAddresses(username)
    if commodity not in addys or len(addys[commodity]) < 3:
        imp = subprocess.check_output([
            'find',
            '%sledger/%s/' % (TIGO_HOME, commodity),
            '-size',
            '0',
            '-name',
            'included.dat'
        ]).split('included.dat')
        chosen = random.randint(0, len(imp) - 1)
        imp[chosen] = imp[chosen].replace('%sledger/%s' % (TIGO_HOME, commodity), '')
        found = re.search('[^/]\w*[^/]', imp[chosen]).group(0)
        f = open('%sledger/%s/%s/included.dat' % (TIGO_HOME, commodity, found), 'w')
        f.write(';ptyglass:%s' % username)
        f.close()
    return redirect(url_for('identity', username=username))


if __name__ == '__main__':
    app.run()
