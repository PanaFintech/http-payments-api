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
    kwargs['prices'] = {'BTC': 0, 'DASH': 0}
    search = "P"
    try:
        grep = subprocess.check_output([
            'grep',
            '-r',
            search, '%sledger/prices/' % TIGO_HOME
        ])
        if (grep and len(grep) > 1):
            kwargs['prices'] = {
                'BTC': Decimal(re.search('\$ .[ 0-9.]*BTC', grep).group(0).replace('BTC', '').replace('$', '').replace(' ', '')),
                'DASH': Decimal(re.search('\$ .[ 0-9.]*DASH', grep).group(0).replace('DASH', '').replace('$', '').replace(' ', ''))
            }
            kwargs['prices']['BTC'] = kwargs['prices']['BTC'].quantize(Decimal(0.001))
            kwargs['prices']['DASH'] = kwargs['prices']['DASH'].quantize(Decimal(0.001))
    except Exception as e:
        print(e)
    print(kwargs)
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
    return addys

def mkdirp(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == os.errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

@app.route('/id/<username>')
def identity(username=None):
    if (username):
        depAddys = getAddresses(username)
        return ptyRender({'username':username, 'depositAddresses':depAddys})
    return ptyRender()

@app.route('/address/generate/<commodity>/<username>')
def genaddress(commodity, username):
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
    # TODO return json encoded address and price.
    return redirect(url_for('identity', username=username))

if __name__ == '__main__':
    app.run()
