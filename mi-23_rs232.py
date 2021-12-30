# Copyright (C) 2021 by Muck van Weerdenburg
#
# Protocol description at http://mweerden.net/mi-23_rs232.html


import argparse
import termios
import time
import tty


argument_parser = argparse.ArgumentParser(description='Read measurement data from Hapé MI-23 MK3 and similar devices via serial connection.')
argument_parser.add_argument('-f', '--file', metavar='DEVICE', default='/dev/ttyS0', help='serial device to use for input (default: /dev/ttyS0)')
argument_parser.add_argument('-c', '--csv', action='store_true', help='output measurements in CSV format')
argument_parser.add_argument('-v', '--value', action='store_true', help='output value only')
argument_parser.add_argument('-n', '--new-lines', action='store_true', help='write each measurement on a new line instead of replacing the previous one')


# bits: abcdefg
#
# segments:
#      c
#   b     g
#      f
#   a     e
#      d
#
to_7segment_digit = {
 0x00 : ' ',
 0x15 : '7',
 0x1f : '3',
 0x27 : '4',
 0x3e : '5',
 0x3f : '9',
 0x5b : '2',
 0x68 : 'L',
 0x7d : '0',
 0x7e : '6',
 0x7f : '8',
 0x05 : '1',
}

# byte index (zero-based), bit -> prefix
unit_prefixes = {
  (9, 0x8): 'u',
  (9, 0x4): 'n',
  (9, 0x2): 'k',
  (10, 0x8): 'm',
  (10, 0x2): 'M',
}

# byte index (zero-based), bit -> unit
units = {
  (10, 0x4): '%',
  (11, 0x8): 'F',
  (11, 0x4): 'Ohm',
  (12, 0x8): 'A',
  (12, 0x4): 'V',
  (12, 0x2): 'Hz',
  (13, 0x4): 'C',
}

# byte index (zero-based), bit -> option
options = {
  (0, 0x8): 'AC',
  (0, 0x4): 'DC',
  (0, 0x2): 'auto',
  (0, 0x1): 'rs232',
  (9, 0x1): 'diode',
  (10, 0x1): 'buzzer',
  (11, 0x2): 'relative',
}



arguments = argument_parser.parse_args()

fd = open(arguments.file, 'rb')
tty.setraw(fd)
tty_attributes = termios.tcgetattr(fd)
tty_attributes[4] = termios.B2400 
tty_attributes[5] = termios.B2400 # seems to be the only one that actually changes the speed
termios.tcsetattr(fd, termios.TCSAFLUSH, tty_attributes)


byte_buffer = []
last_output_length = 0
while True:
  new_byte = ord(fd.read(1))
  new_timestamp = time.time()

  byte_buffer.append((new_timestamp, new_byte))

  # detect full measurement on last byte and by checking indices
  if new_byte & 0xf0 == 0xe0 and len(byte_buffer) >= 14 and \
     [ b[1] >> 4 for b in byte_buffer[-14:] ] == list(range(1,15)):

    # get timestamp from first byte and extract data nibbles only
    # ignore additional bytes before the measurement (noise or interrupted data)
    timestamp = byte_buffer[-14][0]
    data_nibbles = [ b[1] & 0x0f for b in byte_buffer[-14:] ]
    byte_buffer = []


    digits = ''
    for i in range(1,9,2):
      digit_byte = (data_nibbles[i] << 4) | data_nibbles[i+1]

      if digit_byte & 0x80:
        if i == 1:
          digits += '-'
        else:
          digits += '.'

      digits += to_7segment_digit.get(digit_byte & 0x7f,'?')


    unit_prefix = ''
    for i, b in unit_prefixes:
      if data_nibbles[i] & b != 0:
        unit_prefix = unit_prefixes[(i,b)]


    unit = ''
    for i, b in units:
      if data_nibbles[i] & b != 0:
        unit = units[(i,b)]


    enabled_options = []
    for i, b in options:
      if data_nibbles[i] & b != 0:
        enabled_options.append(options[(i,b)])


    if arguments.value:
      output = digits
    else:
      if arguments.csv:
        output = '{:.2f},{},{}{},"{}"'.format(timestamp, digits,
                unit_prefix, unit, ','.join(enabled_options))
      else:
        if len(enabled_options) == 0:
          enabled_options = ''
        else:
          enabled_options = '(' + ', '.join(enabled_options) + ')'
        output = '{:.2f} {} {}{} {}'.format(timestamp, digits,
                unit_prefix, unit, enabled_options)
    
    if not arguments.csv and not arguments.new_lines:
      print('\r', ' '*last_output_length, '\r', output,
                sep='', end='', flush=True)
    else:
      print(output)
    last_output_length = len(output)
