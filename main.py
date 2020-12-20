import argparse
import os
import base64
import xml.etree.ElementTree as ET
from clint.textui import progress
import request
import crypt
import fusclient
import versionfetch

def Download(args, version):
    client = fusclient.FUSClient()
    path, filename, size = getbinaryfile(client, version, args.dev_model, args.dev_region)
    out = os.path.join('.', filename)
    dloffset = os.stat(out).st_size
    if dloffset == size:
        print("Already downloaded.")
        return out
    with open(out, "ab") as fd:
        initdownload(client, filename)
        r = client.downloadfile(path+filename, dloffset)
        if "Content-MD5" in r.headers:
            print("MD5:", base64.b64decode(r.headers["Content-MD5"]).hex())
        # TODO: use own progress bar instead of clint
        for chunk in progress.bar(r.iter_content(chunk_size=0x10000), expected_size=((size-dloffset)/0x10000)+1):
            if chunk:
                fd.write(chunk)
                fd.flush()
    return out

def Run():
    #tacle arguments
    parser = argparse.ArgumentParser(description="Download and query firmware for Samsung devices.")
    parser.add_argument("-m", "--dev-model", help="device region code", required=True)
    parser.add_argument("-r", "--dev-region", help="device model", required=True)
    args = parser.parse_args()
    if args.dev_model == '' or args.dev_region == '':
        parser.print_help()
        sys.exit(1)
    
    #get latest version first
    print("Getting latest version...")
    version = versionfetch.getlatestver(args.dev_model, args.dev_region)
    print("Latest version is ", version)
    
    #download with resume
    enc_file = ""
    for i in range(100):
        print("Downloading...")
        try:
            enc_file = Download(args, version)
        except:
            print("Download failed, %d time retry..." % i+1)
            continue
        print("Download succeed.")
        break 

    #check downloaded file
    if enc_file == "":
        print("Downloaded file not exists.")
        sys.exit(1)
    print("Downloaded enc file name: ", enc_file)
        
    #get output zip file name
    zip_file = ''
    pos = enc_file.find("enc4")
    if pos != 0:
       zip_file = enc_file[:pos-1]
       
    #check zip file
    if zip_file[-3:] != "zip":
        print("Downloaded file incorrect.")
        sys.exit(1)
    print("Downloaded zip file name: ", zip_file)
            
    #decrypt file
    print("Decompressing...")
    getkey = crypt.getv4key
    key = getkey(version, args.dev_model, args.dev_region)
    length = os.stat(enc_file).st_size
    with open(enc_file, "rb") as inf:
        with open(zip_file, "wb") as outf:
            crypt.decrypt_progress(inf, outf, key, length)
    print("Decompress done.")

def initdownload(client, filename):
    req = request.binaryinit(filename, client.nonce)
    resp = client.makereq("NF_DownloadBinaryInitForMass.do", req)

def getbinaryfile(client, fw, model, region):
    req = request.binaryinform(fw, model, region, client.nonce)
    resp = client.makereq("NF_DownloadBinaryInform.do", req)
    root = ET.fromstring(resp)
    status = int(root.find("./FUSBody/Results/Status").text)
    if status != 200:
        raise Exception("DownloadBinaryInform returned {}, firmware could not be found?".format(status))
    size = int(root.find("./FUSBody/Put/BINARY_BYTE_SIZE/Data").text)
    filename = root.find("./FUSBody/Put/BINARY_NAME/Data").text
    path = root.find("./FUSBody/Put/MODEL_PATH/Data").text
    return path, filename, size
    
if __name__ == '__main__':
    Run()
