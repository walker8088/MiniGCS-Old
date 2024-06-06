#!/usr/bin/env python

#
# Serial firmware uploader for the PX4FMU bootloader
#
# The PX4 firmware file is a JSON-encoded Python object, containing
# metadata fields and a zlib-compressed base64-encoded firmware image.
#
# The uploader uses the following fields from the firmware file:
#
# image
#       The firmware that will be uploaded.
# image_size
#       The size of the firmware in bytes.
# board_id
#       The board for which the firmware is intended.
# board_revision
#       Currently only used for informational purposes.
#

import sys
import argparse
import binascii
import serial
import struct
import json
import zlib
import base64
import time
import array

from sys import platform as _platform


class firmware(object):
    '''Loads a firmware file'''

    desc = {}
    image = bytes()
    crctab = array.array('I', [
        0x00000000, 0x77073096, 0xee0e612c, 0x990951ba, 0x076dc419, 0x706af48f,
        0xe963a535, 0x9e6495a3, 0x0edb8832, 0x79dcb8a4, 0xe0d5e91e, 0x97d2d988,
        0x09b64c2b, 0x7eb17cbd, 0xe7b82d07, 0x90bf1d91, 0x1db71064, 0x6ab020f2,
        0xf3b97148, 0x84be41de, 0x1adad47d, 0x6ddde4eb, 0xf4d4b551, 0x83d385c7,
        0x136c9856, 0x646ba8c0, 0xfd62f97a, 0x8a65c9ec, 0x14015c4f, 0x63066cd9,
        0xfa0f3d63, 0x8d080df5, 0x3b6e20c8, 0x4c69105e, 0xd56041e4, 0xa2677172,
        0x3c03e4d1, 0x4b04d447, 0xd20d85fd, 0xa50ab56b, 0x35b5a8fa, 0x42b2986c,
        0xdbbbc9d6, 0xacbcf940, 0x32d86ce3, 0x45df5c75, 0xdcd60dcf, 0xabd13d59,
        0x26d930ac, 0x51de003a, 0xc8d75180, 0xbfd06116, 0x21b4f4b5, 0x56b3c423,
        0xcfba9599, 0xb8bda50f, 0x2802b89e, 0x5f058808, 0xc60cd9b2, 0xb10be924,
        0x2f6f7c87, 0x58684c11, 0xc1611dab, 0xb6662d3d, 0x76dc4190, 0x01db7106,
        0x98d220bc, 0xefd5102a, 0x71b18589, 0x06b6b51f, 0x9fbfe4a5, 0xe8b8d433,
        0x7807c9a2, 0x0f00f934, 0x9609a88e, 0xe10e9818, 0x7f6a0dbb, 0x086d3d2d,
        0x91646c97, 0xe6635c01, 0x6b6b51f4, 0x1c6c6162, 0x856530d8, 0xf262004e,
        0x6c0695ed, 0x1b01a57b, 0x8208f4c1, 0xf50fc457, 0x65b0d9c6, 0x12b7e950,
        0x8bbeb8ea, 0xfcb9887c, 0x62dd1ddf, 0x15da2d49, 0x8cd37cf3, 0xfbd44c65,
        0x4db26158, 0x3ab551ce, 0xa3bc0074, 0xd4bb30e2, 0x4adfa541, 0x3dd895d7,
        0xa4d1c46d, 0xd3d6f4fb, 0x4369e96a, 0x346ed9fc, 0xad678846, 0xda60b8d0,
        0x44042d73, 0x33031de5, 0xaa0a4c5f, 0xdd0d7cc9, 0x5005713c, 0x270241aa,
        0xbe0b1010, 0xc90c2086, 0x5768b525, 0x206f85b3, 0xb966d409, 0xce61e49f,
        0x5edef90e, 0x29d9c998, 0xb0d09822, 0xc7d7a8b4, 0x59b33d17, 0x2eb40d81,
        0xb7bd5c3b, 0xc0ba6cad, 0xedb88320, 0x9abfb3b6, 0x03b6e20c, 0x74b1d29a,
        0xead54739, 0x9dd277af, 0x04db2615, 0x73dc1683, 0xe3630b12, 0x94643b84,
        0x0d6d6a3e, 0x7a6a5aa8, 0xe40ecf0b, 0x9309ff9d, 0x0a00ae27, 0x7d079eb1,
        0xf00f9344, 0x8708a3d2, 0x1e01f268, 0x6906c2fe, 0xf762575d, 0x806567cb,
        0x196c3671, 0x6e6b06e7, 0xfed41b76, 0x89d32be0, 0x10da7a5a, 0x67dd4acc,
        0xf9b9df6f, 0x8ebeeff9, 0x17b7be43, 0x60b08ed5, 0xd6d6a3e8, 0xa1d1937e,
        0x38d8c2c4, 0x4fdff252, 0xd1bb67f1, 0xa6bc5767, 0x3fb506dd, 0x48b2364b,
        0xd80d2bda, 0xaf0a1b4c, 0x36034af6, 0x41047a60, 0xdf60efc3, 0xa867df55,
        0x316e8eef, 0x4669be79, 0xcb61b38c, 0xbc66831a, 0x256fd2a0, 0x5268e236,
        0xcc0c7795, 0xbb0b4703, 0x220216b9, 0x5505262f, 0xc5ba3bbe, 0xb2bd0b28,
        0x2bb45a92, 0x5cb36a04, 0xc2d7ffa7, 0xb5d0cf31, 0x2cd99e8b, 0x5bdeae1d,
        0x9b64c2b0, 0xec63f226, 0x756aa39c, 0x026d930a, 0x9c0906a9, 0xeb0e363f,
        0x72076785, 0x05005713, 0x95bf4a82, 0xe2b87a14, 0x7bb12bae, 0x0cb61b38,
        0x92d28e9b, 0xe5d5be0d, 0x7cdcefb7, 0x0bdbdf21, 0x86d3d2d4, 0xf1d4e242,
        0x68ddb3f8, 0x1fda836e, 0x81be16cd, 0xf6b9265b, 0x6fb077e1, 0x18b74777,
        0x88085ae6, 0xff0f6a70, 0x66063bca, 0x11010b5c, 0x8f659eff, 0xf862ae69,
        0x616bffd3, 0x166ccf45, 0xa00ae278, 0xd70dd2ee, 0x4e048354, 0x3903b3c2,
        0xa7672661, 0xd06016f7, 0x4969474d, 0x3e6e77db, 0xaed16a4a, 0xd9d65adc,
        0x40df0b66, 0x37d83bf0, 0xa9bcae53, 0xdebb9ec5, 0x47b2cf7f, 0x30b5ffe9,
        0xbdbdf21c, 0xcabac28a, 0x53b39330, 0x24b4a3a6, 0xbad03605, 0xcdd70693,
        0x54de5729, 0x23d967bf, 0xb3667a2e, 0xc4614ab8, 0x5d681b02, 0x2a6f2b94,
        0xb40bbe37, 0xc30c8ea1, 0x5a05df1b, 0x2d02ef8d
    ])
    crcpad = bytearray(b'\xff\xff\xff\xff')

    def __init__(self, path):

        # read the file
        f = open(path, "r")
        self.desc = json.load(f)
        f.close()

        self.image = bytearray(
            zlib.decompress(base64.b64decode(self.desc['image'])))

        # pad image to 4-byte length
        while ((len(self.image) % 4) != 0):
            self.image.append('\xff')

    def property(self, propname):
        return self.desc[propname]

    def __crc32(self, bytes, state):
        for byte in bytes:
            index = (state ^ byte) & 0xff
            state = self.crctab[index] ^ (state >> 8)
        return state

    def crc(self, padlen):
        state = self.__crc32(self.image, int(0))
        for i in range(len(self.image), (padlen - 1), 4):
            state = self.__crc32(self.crcpad, state)
        return state


class uploader(object):
    '''Uploads a firmware file to the PX FMU bootloader'''

    # protocol bytes
    INSYNC = b'\x12'
    EOC = b'\x20'

    # reply bytes
    OK = b'\x10'
    FAILED = b'\x11'
    INVALID = b'\x13'  # rev3+

    # command bytes
    NOP = b'\x00'  # guaranteed to be discarded by the bootloader
    GET_SYNC = b'\x21'
    GET_DEVICE = b'\x22'
    CHIP_ERASE = b'\x23'
    CHIP_VERIFY = b'\x24'  # rev2 only
    PROG_MULTI = b'\x27'
    READ_MULTI = b'\x28'  # rev2 only
    GET_CRC = b'\x29'  # rev3+
    REBOOT = b'\x30'

    INFO_BL_REV = b'\x01'  # bootloader protocol revision
    BL_REV_MIN = 2  # minimum supported bootloader protocol
    BL_REV_MAX = 4  # maximum supported bootloader protocol
    INFO_BOARD_ID = b'\x02'  # board type
    INFO_BOARD_REV = b'\x03'  # board revision
    INFO_FLASH_SIZE = b'\x04'  # max firmware size in bytes

    PROG_MULTI_MAX = 60  # protocol max is 255, must be multiple of 4
    READ_MULTI_MAX = 60  # protocol max is 255, something overflows with >= 64

    NSH_INIT = bytearray(b'\x0d\x0d\x0d')
    NSH_REBOOT_BL = b"reboot -b\n"
    NSH_REBOOT = b"reboot\n"
    MAVLINK_REBOOT_ID1 = bytearray(
        b'\xfe\x21\x72\xff\x00\x4c\x00\x00\x80\x3f\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xf6\x00\x01\x00\x00\x48\xf0'
    )
    MAVLINK_REBOOT_ID0 = bytearray(
        b'\xfe\x21\x45\xff\x00\x4c\x00\x00\x80\x3f\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xf6\x00\x00\x00\x00\xd7\xac'
    )

    def __init__(self, portname, baudrate):
        # open the port, keep the default timeout short so we can poll quickly
        self.port = serial.Serial(portname, baudrate, timeout=0.5)

    def close(self):
        if self.port is not None:
            self.port.close()

    def __send(self, c):
        #               print("send " + binascii.hexlify(c))
        self.port.write(c)

    def __recv(self, count=1):
        c = self.port.read(count)
        if len(c) < 1:
            raise RuntimeError("timeout waiting for data")
#               print("recv " + binascii.hexlify(c))
        return c

    def __recv_int(self):
        raw = self.__recv(4)
        val = struct.unpack("<I", raw)
        return val[0]

    def __getSync(self):
        self.port.flush()
        c = bytes(self.__recv())
        if c != self.INSYNC:
            raise RuntimeError("unexpected %s instead of INSYNC" % c)
        c = self.__recv()
        if c == self.INVALID:
            raise RuntimeError("bootloader reports INVALID OPERATION")
        if c == self.FAILED:
            raise RuntimeError("bootloader reports OPERATION FAILED")
        if c != self.OK:
            raise RuntimeError("unexpected response 0x%x instead of OK" %
                               ord(c))

    # attempt to get back into sync with the bootloader
    def __sync(self):
        # send a stream of ignored bytes longer than the longest possible conversation
        # that we might still have in progress
        #               self.__send(uploader.NOP * (uploader.PROG_MULTI_MAX + 2))
        self.port.flushInput()
        self.__send(uploader.GET_SYNC + uploader.EOC)
        self.__getSync()

#       def __trySync(self):
#               c = self.__recv()
#               if (c != self.INSYNC):
#                       #print("unexpected 0x%x instead of INSYNC" % ord(c))
#                       return False;
#               c = self.__recv()
#               if (c != self.OK):
#                       #print("unexpected 0x%x instead of OK" % ord(c))
#                       return False
#               return True

# send the GET_DEVICE command and wait for an info parameter

    def __getInfo(self, param):
        self.__send(uploader.GET_DEVICE + param + uploader.EOC)
        value = self.__recv_int()
        self.__getSync()
        return value

    # send the CHIP_ERASE command and wait for the bootloader to become ready
    def __erase(self):
        self.__send(uploader.CHIP_ERASE + uploader.EOC)
        # erase is very slow, give it 20s
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                self.__getSync()
                return
            except RuntimeError:
                # we timed out, that's OK
                continue

        raise RuntimeError("timed out waiting for erase")

    # send a PROG_MULTI command to write a collection of bytes
    def __program_multi(self, data):

        if runningPython3 == True:
            length = len(data).to_bytes(1, byteorder='big')
        else:
            length = chr(len(data))

        self.__send(uploader.PROG_MULTI)
        self.__send(length)
        self.__send(data)
        self.__send(uploader.EOC)
        self.__getSync()

    # verify multiple bytes in flash
    def __verify_multi(self, data):

        if runningPython3 == True:
            length = len(data).to_bytes(1, byteorder='big')
        else:
            length = chr(len(data))

        self.__send(uploader.READ_MULTI)
        self.__send(length)
        self.__send(uploader.EOC)
        self.port.flush()
        programmed = self.__recv(len(data))
        if programmed != data:
            print(("got    " + binascii.hexlify(programmed)))
            print(("expect " + binascii.hexlify(data)))
            return False
        self.__getSync()
        return True

    # send the reboot command
    def __reboot(self):
        self.__send(uploader.REBOOT + uploader.EOC)
        self.port.flush()

        # v3+ can report failure if the first word flash fails
        if self.bl_rev >= 3:
            self.__getSync()

    # split a sequence into a list of size-constrained pieces
    def __split_len(self, seq, length):
        return [seq[i:i + length] for i in range(0, len(seq), length)]

    # upload code
    def __program(self, fw):
        code = fw.image
        groups = self.__split_len(code, uploader.PROG_MULTI_MAX)
        for bytes in groups:
            self.__program_multi(bytes)

    # verify code
    def __verify_v2(self, fw):
        self.__send(uploader.CHIP_VERIFY + uploader.EOC)
        self.__getSync()
        code = fw.image
        groups = self.__split_len(code, uploader.READ_MULTI_MAX)
        for bytes in groups:
            if (not self.__verify_multi(bytes)):
                raise RuntimeError("Verification failed")

    def __verify_v3(self, fw):
        expect_crc = fw.crc(self.fw_maxsize)
        self.__send(uploader.GET_CRC + uploader.EOC)
        report_crc = self.__recv_int()
        self.__getSync()
        if report_crc != expect_crc:
            print(("Expected 0x%x" % expect_crc))
            print(("Got      0x%x" % report_crc))
            raise RuntimeError("Program CRC failed")

    # get basic data about the board
    def identify(self):
        # make sure we are in sync before starting
        self.__sync()

        # get the bootloader protocol ID first
        self.bl_rev = self.__getInfo(uploader.INFO_BL_REV)
        if (self.bl_rev < uploader.BL_REV_MIN) or (self.bl_rev >
                                                   uploader.BL_REV_MAX):
            print(("Unsupported bootloader protocol %d" % uploader.INFO_BL_REV))
            raise RuntimeError("Bootloader protocol mismatch")

        self.board_type = self.__getInfo(uploader.INFO_BOARD_ID)
        self.board_rev = self.__getInfo(uploader.INFO_BOARD_REV)
        self.fw_maxsize = self.__getInfo(uploader.INFO_FLASH_SIZE)

    # upload the firmware
    def upload(self, fw):
        # Make sure we are doing the right thing
        if self.board_type != fw.property('board_id'):
            raise RuntimeError("Firmware not suitable for this board")
        if self.fw_maxsize < fw.property('image_size'):
            raise RuntimeError("Firmware image is too large for this board")

        print("erase...")
        self.__erase()

        print("program...")
        self.__program(fw)

        print("verify...")
        if self.bl_rev == 2:
            self.__verify_v2(fw)
        else:
            self.__verify_v3(fw)

        print("done, rebooting.")
        self.__reboot()
        self.port.close()

    def send_reboot(self):
        # try reboot via NSH first
        self.__send(uploader.NSH_INIT)
        self.__send(uploader.NSH_REBOOT_BL)
        self.__send(uploader.NSH_INIT)
        self.__send(uploader.NSH_REBOOT)
        # then try MAVLINK command
        self.__send(uploader.MAVLINK_REBOOT_ID1)
        self.__send(uploader.MAVLINK_REBOOT_ID0)


# Detect python version
if sys.version_info[0] < 3:
    runningPython3 = False
else:
    runningPython3 = True

# Parse commandline arguments
parser = argparse.ArgumentParser(
    description="Firmware uploader for the PX autopilot system.")
parser.add_argument('--port',
                    action="store",
                    required=True,
                    help="Serial port(s) to which the FMU may be attached")
parser.add_argument(
    '--baud',
    action="store",
    type=int,
    default=115200,
    help=
    "Baud rate of the serial port (default is 115200), only required for true serial ports."
)
parser.add_argument('firmware',
                    action="store",
                    help="Firmware file to be uploaded")
args = parser.parse_args()

# Load the firmware file
fw = firmware(args.firmware)
print(("Loaded firmware for %x,%x, waiting for the bootloader..." %
      (fw.property('board_id'), fw.property('board_revision'))))

# Spin waiting for a device to show up
while True:
    portlist = []
    patterns = args.port.split(",")
    # on unix-like platforms use glob to support wildcard ports. This allows
    # the use of /dev/serial/by-id/usb-3D_Robotics on Linux, which prevents the upload from
    # causing modem hangups etc
    if "linux" in _platform or "darwin" in _platform:
        import glob
        for pattern in patterns:
            portlist += glob.glob(pattern)
    else:
        portlist = patterns

    for port in portlist:

        #print("Trying %s" % port)

        # create an uploader attached to the port
        try:
            if "linux" in _platform:
                # Linux, don't open Mac OS and Win ports
                if not "COM" in port and not "tty.usb" in port:
                    up = uploader(port, args.baud)
            elif "darwin" in _platform:
                # OS X, don't open Windows and Linux ports
                if not "COM" in port and not "ACM" in port:
                    up = uploader(port, args.baud)
            elif "win" in _platform:
                # Windows, don't open POSIX ports
                if not "/" in port:
                    up = uploader(port, args.baud)
        except:
            # open failed, rate-limit our attempts
            time.sleep(0.05)

            # and loop to the next port
            continue

        # port is open, try talking to it
        try:
            # identify the bootloader
            up.identify()
            print(("Found board %x,%x bootloader rev %x on %s" %
                  (up.board_type, up.board_rev, up.bl_rev, port)))

        except:
            # most probably a timeout talking to the port, no bootloader, try to reboot the board
            print(("attempting reboot on %s..." % port))
            up.send_reboot()
            # wait for the reboot, without we might run into Serial I/O Error 5
            time.sleep(0.5)
            continue

        try:
            # ok, we have a bootloader, try flashing it
            up.upload(fw)

        except RuntimeError as ex:

            # print the error
            print(("ERROR: %s" % ex.args))

        finally:
            # always close the port
            up.close()

        # we could loop here if we wanted to wait for more boards...
        sys.exit(0)
