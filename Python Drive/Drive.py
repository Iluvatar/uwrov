# NOTE: This is not fully functional yet. As in, it still doesn't work properly.
# This is the dev version.
# Made for Python 2.7

import math, pygame, serial
from serial import Serial, SerialException, SerialTimeoutException
from time import sleep
from pprint import pprint


"""
      Front

 FT_LT     FT_RT
   /---------\
  /|         |\
   |  FT_VL  |
   |    o    |
   |         |
   |    o    |
   |  BK_VL  |
  \|         |/
   \---------/
 BK_LT     BK_RT

"""

class Motor:
    def __init__(self, ID, pow_header, dir_header, power = 0):
        self.ID = ID
        self.pow_header = pow_header
        self.dir_header = dir_header
        self.power = power

class MOTOR:
    FT_LT = 1 # front left
    FT_RT = 2 # front right
    BK_RT = 3 # back right
    BK_LT = 4 # back left
    FT_VL = 5 # front vertical
    BK_VL = 6 # back vertical

# values in range [0, 1]
class Control:
    def __init__(self, trans_x = 0, trans_y = 0, yaw = 0, rise = 0,
                 trans_x_tare = 0, trans_y_tare = 0, yaw_tare = 0, rise_tare = 0,
                 rise_control = 0):
        self.trans_x = trans_x
        self.trans_y = trans_y
        self.yaw = yaw
        self.rise = rise
        self.trans_x_tare = trans_x_tare
        self.trans_y_tare = trans_y_tare
        self.yaw_tare = yaw_tare
        self.rise_tare = rise_tare
        self.rise_control = rise_control

    def tare(self):
        self.trans_x_tare = self.trans_x
        self.trans_y_tare = self.trans_y
        self.yaw_tare = self.yaw
        self.rise_tare = self.rise

    def trans_x_value(self):
        return self.trans_x - self.trans_x_tare

    def trans_y_value(self):
        return self.trans_y - self.trans_y_tare

    def yaw_value(self):
        return self.yaw - self.yaw_tare

    def rise_value(self):
        return self.rise - self.rise_tare + self.rise_control

ser = None
control = Control()

motors = {MOTOR.FT_LT: Motor(MOTOR.FT_LT, b'1', b'a'),
          MOTOR.FT_RT: Motor(MOTOR.FT_RT, b'2', b'b'),
          MOTOR.BK_RT: Motor(MOTOR.BK_RT, b'3', b'c'),
          MOTOR.BK_LT: Motor(MOTOR.BK_LT, b'4', b'd'),
          MOTOR.FT_VL: Motor(MOTOR.FT_VL, b'5', b'e'),
          MOTOR.BK_VL: Motor(MOTOR.BK_VL, b'6', b'f')}

# range 0 to 255
# pressure, humidity, temperature, current
sensor_values = {b'P': 0, b'H': 0, b'T': 0, b'C': 0}

def connect(port_name):
    """Returns a Serial object that is connected to the port_name. Returns
    None if the connection could not be made."""

    try:
        return Serial(port_name, timeout = .5, writeTimeout = .5)
    except SerialException:
        print "connect: could not connect to port", port_name
        return None


def read_data_values(ser, data_values):
    """Reads data from ser and updates the dict data_values.
    
    The keys in data_values should be bytes that are the headers for sensor
    values. Attempts to find each key in the read data and then updates it if
    the next two bytes are consistent."""

    if not isinstance(data_values, dict):
        raise ValueError("read_data_values: data_values not of type dict")
    if not isinstance(ser, Serial):
        raise ValueError("read_data_values: ser not of type Serial")

    # so we don't read too much data
    read_chars = min(ser.inWaiting(), len(data_values) * 5)
    raw_data = ser.read(read_chars)

    for key in data_values.keys():
        pos = raw_data[:-1].rfind(key)
        if pos != -1:
            data_values[key] = raw_data[pos + 1]

    if read_chars > 12:
        ser.flushInput()


def write_motor_values(ser):
    """Writes the motor power and direction to the serial port.
    
    Each write consists of a header followed by the value repeated twice."""

    # do something about this
    global motors

    if not isinstance(ser, Serial):
        raise ValueError("write_motor_values: ser not of type Serial, of type",
                         type(ser))
    for motor in motors:
        pow = motors[motor].power
        dir = b'1' if pow > 0 else b'0'
        ser.write(motors[motor].pow_header + bytes([int(abs(pow))] * 2))
        ser.write(motors[motor].dir_header + dir * 2)





def update_motor_values(control):
    # do something about this
    global motors

    for motor in motors:
        motors[motor].power = get_motor_power(motor, control)

def get_motor_power(n, control):
    """Takes the motor number and returns the magnitude of the total power it
    should output, from -255 to 255. Returns 0 if an invalid motor is given."""

    power_sum = get_trans_power(n, control) + get_yaw_power(n, control) + \
                get_rise_power(n, control)
    scaled_power = int(power_sum * 255)
    try:
        return min(scaled_power, 255) if scaled_power > 0 else max(scaled_power, -255)
    except ValueError as bad_motor:
        print bad_motor.args[0]
        return 0


def get_trans_power(n, control):
    """Takes the motor number and returns the power it should output for
    translational motion, from -1 to 1.
    
    Raises a ValueError if the motor number is unrecognized."""
    
    # these motors don't have an effect on translational speed
    if n == MOTOR.FT_VL or n == MOTOR.BK_VL:
        return 0
        
    x = control.trans_x_value()
    y = control.trans_y_value()
    if x == 0 and y == 0:
        return 0
    
    m1 = .5 * x + y / (2 * math.sqrt(3))
    m2 = -.5 * x + y / (2 * math.sqrt(3))
    m1_norm = m1 / abs(max(m1, m2)) * min(math.hypot(x, y), 1)
    m2_norm = m2 / abs(max(m1, m2)) *  min(math.hypot(x, y), 1)
    if n == MOTOR.FT_LT:
        return -1 * m1_norm
    if n == MOTOR.FT_RT:
        return -1 * m2_norm
    if n == MOTOR.BK_RT:
        return m1_norm
    if n == MOTOR.BK_LT:
        return m2_norm
    raise ValueError("get_trans_power: Illegal motor number")


def get_yaw_power(n, control):
    """Takes the motor number and returns the power it should output for
    rotational motion, from -1 to 1.
    
    Raises a ValueError if the motor number is unrecognized."""

    # these motors don't have an effect on translational speed
    if n == MOTOR.FT_VL or n == MOTOR.BK_VL:
        return 0
    if n == MOTOR.FT_LT or n == MOTOR.BK_RT:
        return -.4 * control.yaw_value()
    if n == MOTOR.FT_RT or n == MOTOR.BK_LT:
        return .4 * control.yaw_value()
    raise ValueError("get_yaw_power: Illegal motor number")


def get_rise_power(n, control):
    """Takes the motor number and returns the power it should output for
    vertical motion, from -1 to 1.
    
    Raises a ValueError if the motor number is unrecognized."""

    # these motors don't have an effect on translational speed
    if n == MOTOR.FT_LT or n == MOTOR.BK_RT or \
       n == MOTOR.FT_RT or n == MOTOR.BK_LT:
        return 0
    if n == MOTOR.FT_VL or n == MOTOR.BK_VL:
        return control.rise_value()
    raise ValueError("get_rise_power: Illegal motor number")




def update_joy_values(joystick, control):
    control.trans_x = joystick.get_axis(0)
    control.trans_y = -1 * joystick.get_axis(1)
    control.rise = -1 * joystick.get_axis(2)
    control.yaw = joystick.get_axis(4)

def process_joy_events():
    for event in pygame.event.get():
        if event.type == pygame.JOYBUTTONDOWN and event.__dict__["button"] == 1:
            control.tare()
        if event.type == pygame.JOYBUTTONDOWN and event.__dict__["button"] == 0:
            if control.rise_control > -1:
                control.rise_control -= .05
        if event.type == pygame.JOYBUTTONDOWN and event.__dict__["button"] == 3:
            if control.rise_control < 1:
                control.rise_control += .05

def joy_init():
    """Initializes pygame and the joystick, and returns the joystick to be
    used."""

    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        raise Exception("joy_init: No joysticks connected")
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    return joystick


def onexit():
    control.trans_x, control.trans_y, control.yaw, control.rise = 0, 0, 0, 0
    control.trans_x_tare, control.trans_y_tare = 0, 0
    control.yaw_tare, control.rise_tare = 0, 0
    update_motor_values()
    write_motor_values(ser)


def print_data_values(data_values):
    if not isinstance(data_values, dict):
        raise ValueError("print_data_values: data_values not of type dict")
    pprint(data_values)



def main():
    joystick = joy_init()
    ser = connect("COM3")

    while True:
        update_joy_values(joystick, control)
        update_motor_values(control)

        try:
            write_motor_values(ser)
        except SerialTimeoutException:
         print "write timeout"

        read_data_values(ser, sensor_values)
        print_data_values(sensor_values)

        process_joy_events()

main()
