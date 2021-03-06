import socket
from threading import Thread
from collections import defaultdict
from datetime import datetime
import os
import time
# from config import channels_dict, ip_server, ip_client, TIME_FORMAT, __version__
from config import channels_dict, TIME_FORMAT, __version__
from ftplib import FTP
import pandas as pd
import sys


def send_via_ftp(session_ftp, path2file, ftp_filename):
    file = open(path2file, 'rb')

    # print('new file name is ', file_prefix + '.csv')

    ### MAYBE FILE IS ALREADY ON THE SERVER
    ftp_files = session_ftp.nlst()

    if ftp_filename in ftp_files:
        print('The file ' + ftp_filename + ' is already on the server. I\'m not gonna rewrite it.')
    else:
        ftp_command = 'STOR ' + ftp_filename
        print(ftp_command)
        try:
            print('Transferring data via FTP...')
            session_ftp.storbinary(ftp_command, file)  # send the file
            print('I didn\'t got an FTP error')
        except:
            print('I got an FTP error :', sys.exc_info())
            print('But probably that\'s ok')

    file.close()


def get_df_total(folder):
    filenames_list = os.listdir(folder)
    filenames_list = sorted([int(filename[:-4]) for filename in filenames_list if filename[-4:] == '.csv'])
    filenames_list = [str(x) + '.csv' for x in filenames_list]
    df_total = None

    for filename in filenames_list:
        df = pd.read_csv(folder + '/' + filename, dtype=str)
        if df_total is None:
            df_total = df
        else:
            df_total = pd.concat([df_total, df], axis=0).reset_index(drop=True)

    return df_total


def get_server_client_ports(channel_id, sensor_id, player_id):
    port_server = '6' + channel_id + sensor_id + player_id
    port_client = '60' + channel_id + sensor_id

    return int(port_server), int(port_client)

def get_socket(ip, port):
    print('Trying to create a socket with ip=' + str(ip) + ', port=' + str(port))
    new_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    new_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    if ip == '':
        new_socket.bind((ip, port))

    return new_socket

# def get_ports_adresses_sockets(ip_server, ip_client, channels_dict, sensor_id, player_id,
#                                get_server_sockets=True, get_client_sockets=False):
def get_ports_adresses_sockets(channels_dict, sensor_id, player_id, ip_server,
                               get_server_sockets=True, get_client_sockets=False):
    ports = defaultdict(dict)
    addresses = defaultdict(dict)
    sockets = defaultdict(dict)
    # TODO: change ip_server and ip_client to <broadcast> and ''

    for channel_name, channel_id in channels_dict.items():
        ports['server'][channel_name], ports['client'][channel_name] = get_server_client_ports(
            channel_id=channel_id,
            sensor_id=sensor_id,
            player_id=player_id)
        # addresses['server'][channel_name] = (ip_server, ports['server'][channel_name])
        # addresses['client'][channel_name] = (ip_client, ports['client'][channel_name])

        # if channel_name == 'cmd':
        #     ip_server = '255.255.255.255'
        #     ip_client = ''
        # else:
        #     ip_client = '255.255.255.255'
        #     ip_server = ''

        # ip_client = '255.255.255.255'
        # ip_server = '255.255.255.255'
        # addresses['server'][channel_name] = (ip_server, ports['server'][channel_name])
        # addresses['client'][channel_name] = (ip_client, ports['client'][channel_name])
        addresses['server'][channel_name] = (ip_server, ports['server'][channel_name])
        # addresses['server'][channel_name] = ('255.255.255.255', ports['server'][channel_name])
        addresses['client'][channel_name] = ('255.255.255.255', ports['client'][channel_name])

        if get_server_sockets:
            # sockets['server'][channel_name] = get_socket(ip_server, ports['server'][channel_name])
            sockets['server'][channel_name] = get_socket('', ports['server'][channel_name])

        if get_client_sockets:
            # sockets['client'][channel_name] = get_socket(ip_client, ports['client'][channel_name])
            sockets['client'][channel_name] = get_socket('', ports['client'][channel_name])

    return ports, addresses, sockets

def time_format2timefile_format(x):
    return x[:19].replace(':', '-')


class SocketThread(Thread):

    def __init__(self, socket, name=None):
        super().__init__()

        self.socket = socket
        if name is not None:
            self.name = name

    def send(self, msg, address):
        """
        :param address: tuple (ip, port)
        :param msg: string message
        """
        self.socket.sendto(msg.encode(), address)


class ListenerThread(SocketThread):

    def __init__(self, *args, verbose=False, **kwargs):
        super().__init__(*args, **kwargs)

        self.verbose = verbose

    def run(self):
        print('Thread ' + self.name + ' are listening...')
        while True:
            msg, addr = self.socket.recvfrom(1024)  # buffer size is 1024 bytes
            msg = msg.decode()
            if self.verbose:
                print("received message:", msg)
                print("sender:", addr)

class FtpThread(Thread):

    def __init__(self, ftp_ip, login, password):
        super().__init__()
        self.ftp_ip = ftp_ip
        self.login = login
        self.password = password
        self.session_ftp = FTP(ftp_ip, login, password)

    def send(self, path2file, ftp_filename):
        send_via_ftp(self.session_ftp, path2file, ftp_filename)


class SenderThread(SocketThread):

    def __init__(self, opponent_address, *args, period=0.5, **kwargs):
        super().__init__(*args, **kwargs)
        self.opponent_address = opponent_address
        self.period = period
        self.periodic_sending = False

    def __repr__(self):
        repr = self.__class__.__name__ + '__' + super().__repr__()
        return repr

    def get_response_msg(self):
        return 'not implemented yet'

    def send(self, msg=None, address=None):
        if msg is None:
            msg = self.get_response_msg()

        if address is None:
            address = self.opponent_address

        self.socket.sendto(msg.encode(), address)

    def run(self):
        while True:
            if self.periodic_sending:
                self.send()

            time.sleep(self.period)


class StatusThread(SenderThread):

    def __init__(self, *args, key_order=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.info_dict = {}
        if key_order is None:
            self.key_order = ['sensor_name', 'version', 'support_cmd', 'status']

    def __setitem__(self, key, value):
        self.info_dict[key] = value

    def __repr__(self):
        repr = self.__class__.__name__ + '__' + super().__repr__() + '__' + str(self.get_response_msg())
        return repr

    def get_response_msg(self):
        response_values = []

        for key in self.key_order:
            value2append = self.info_dict.get(key, '')
            response_values.append(value2append)

        response_msg = ','.join(response_values)

        return response_msg


class TimeThread(SenderThread):
    TIME_THREAD_FORMAT = '%H:%M:%S.%f'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_response_msg(self):
        response_msg = datetime.now().strftime(self.TIME_THREAD_FORMAT)[:-3]

        return response_msg

    # # def send(self, msg=None, address=None):
    # def send(self, msg=None, address='255.255.255.255'):  # Probably this broadcast address is not needed anymore
    #     if msg is None:
    #         msg = self.get_response_msg()
    #
    #     if address is None:
    #         address = self.opponent_address
    #
    #     self.socket.sendto(msg.encode(), address)


class AcknowledgementThread(SenderThread):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ### That's actually the same in this form


class MeasurementsThread(SocketThread):

    def __init__(self,
                 socket,
                 response_address,
                 mpu9250,
                 ftp_thread,
                 # *args,
                 kwargs,
                 package_num=0,
                 ):
        ### WTF??? kwargs doesn't work in the init above
        # super().__init__(socket, *args, **kwargs)
        super().__init__(socket)# , **kwargs)

        self.socket = socket
        # self.response_address = response_address
        self.response_address = response_address  # TODO: WARNING
        self.mpu9250 = mpu9250
        self.ftp_thread = ftp_thread

        self.timestep_detect = kwargs['timestep_detect']
        self.timestep_send = kwargs['timestep_send']
        self.max_time = kwargs['max_time']
        self.verbose = kwargs['verbose']
        self.label = kwargs['label']
        self.person_id = kwargs['person_id']
        self.meta = kwargs['meta']
        self.send_data = kwargs['send_data']
        self.save_data = kwargs['save_data']
        self.folder = kwargs['folder']
        self.synchronize_time = kwargs['synchronize_time']

        self.stop = False  # Stop variable

        self.batch_size = int(self.timestep_send / self.timestep_detect)  # Количество измерений в одном файле
        self.n_batches = int(self.max_time / self.timestep_send)  # Количество отправок
        self.package_num = package_num

    def stop_measurements(self):
        self.stop = True
        print('Stopping')
        # TODO: It loooks like here or nearby I need to create new folders

    @staticmethod
    def get_sleep_time(timestep_detect):
        current_time = time.time()
        time2sleep = timestep_detect - current_time % timestep_detect

        return time2sleep

    def run(self):
        if self.folder is None:
            folder = datetime.now().strftime(TIME_FORMAT)[:-3]
        else:
            folder = self.folder

        self.folder = folder  # FOR THE FTP

        # prefix = '../data/' + folder + '/'
        prefix = '/home/pi/data/' + folder + '/'
        # os.mkdir('../data/' + folder)  # Here we will store data in batches
        os.mkdir(prefix)  # Here we will store data in batches
        data_header = ['datetime_now', 'acc_x', 'acc_y', 'acc_z', 'gyro_x', 'gyro_y', 'gyro_z', 'mag_x', 'mag_y',
                       'mag_z']
        data_header2write = ','.join(data_header) + '\n'

        for n_batch in range(self.n_batches):
            filename = prefix + str(n_batch) + '.csv'
            file = open(filename, 'w')
            file.write(data_header2write)
            for n_measurement in range(self.batch_size):
                data_accelerometer = self.mpu9250.readAccel()
                data_gyroscope = self.mpu9250.readGyro()
                data_magnetometer = self.mpu9250.readMagnet()

                # data_magnetometer = {
                #     'x': -1,
                #     'y': -1,
                #     'z': -1,
                # }

                if self.verbose:
                    if (n_measurement % self.verbose) == 0:
                        print('data_accelerometer: ', data_accelerometer)
                        print('data_gyroscope: ', data_gyroscope)
                        print('data_magnetometer: ', data_magnetometer)

                datetime_current = datetime.now()
                datetime_current_isoformat = datetime_current.isoformat()

                if n_measurement == 0:
                    first_datetime_in_batch = datetime_current.strftime(TIME_FORMAT)
                    first_datetime_in_batch = time_format2timefile_format(first_datetime_in_batch)

                measurement_data = [
                    datetime_current_isoformat,
                    data_accelerometer['x'],
		            data_accelerometer['y'],
                    data_accelerometer['z'],
                    data_gyroscope['x'],
                    data_gyroscope['y'],
                    data_gyroscope['z'],
                    data_magnetometer['x'],
                    data_magnetometer['y'],
                    data_magnetometer['z'],
                ]

                # measurement_data = [str(value) for value in measurement_data]  # Commented on 31 Oct to fix rounding
                for i in range(1, len(measurement_data)):  # Rounding to exactly 3 digits
                    measurement_data[i] = "%.3f" % measurement_data[i]
                    # ### It looks like the trick above is not enough to round to exactly 3 digits.
                    # ### That's why I added the code below
                    # value_parts = measurement_data[i].split('.')
                    # value_parts[1] = value_parts[1][:3]  # Cutting everything after the 3rd digit
                    # measurement_data[i] = '.'.join(value_parts)
                    # # measurement_data[i] = "%.3f" % measurement_data[i]  # TODO: check in google why rounding isn't working

                data2write = ','.join(measurement_data) + '\n'
                file.write(data2write)

                # measurement_data4server = [
                #     str(self.package_num),  # n
                #     measurement_data[0][:-3],  # microseconds are ignored
                # ] + measurement_data[1:]
                #
                # # data2send = str(self.package_num) + ',' + ','.join(measurement_data)  # New line character is not added
                # data2send = ','.join(measurement_data4server)  # New line character is not added
                # if self.send_data:
                #     self.socket.sendto(data2send.encode(), self.response_address)  # TODO: add number of row n

                self.package_num += 1

                if self.stop:
                    break

                if n_measurement != self.batch_size - 1:  # Because if n_measurement != batch_size - 1 we need to consider time for file.close()
                    time2sleep = self.get_sleep_time(self.timestep_detect)
                    time.sleep(time2sleep)

            file.close()

            ftp_filename = 'chair__' + first_datetime_in_batch + '.csv'

            if self.send_data:
                self.ftp_thread.send(filename, ftp_filename)  # ftp_filename should be the 'chair_' + the first date. consider using already implemented functions


            if self.stop:
                break

            time2sleep = self.get_sleep_time(self.timestep_detect)
            time.sleep(time2sleep)


        print('---------------------------')
        print('----End of measurements----')
        print('---------------------------')


class CmdThread(ListenerThread):

    def __init__(self,
                 socket,
                 addresses,
                 status_thread,
                 time_thread,
                 # measurements_thread,
                 acknowledgement_thread,
                 mpu9250,
                 measurement_thread_kwargs,
                 ftp_thread,
                 player_id,
                 *args,
                 verbose=False,
                 sockets=None,
                 **kwargs):
        super().__init__(socket, *args, verbose=verbose, **kwargs)
        self.addresses = addresses
        self.status_thread = status_thread
        self.time_thread = time_thread
        self.time_thread.periodic_sending = True
        # self.measurements_thread = measurements_thread
        self.acknowledgement_thread = acknowledgement_thread
        self.mpu9250 = mpu9250
        self.measurement_thread_kwargs = measurement_thread_kwargs
        self.sockets = sockets
        self.package_num = 0  # For measurements_thread
        self.player_id = player_id
        self.ftp_thread = ftp_thread
        # self.last_ftp_file_prefix = None

    # @staticmethod
    def stop_measurements(self, measurements_thread):
        print('Trying to stop')
        if measurements_thread is None:
            print('measurements_thread is None, please initialize it beforehand')
        else:
            measurements_thread.stop_measurements()
            self.package_num = measurements_thread.package_num
            measurements_thread.join()
            print('Measurements thread is killed')

    # def get_measurements_thread(self, socket, response_address, mpu9250, measurement_thread_kwargs):
    #     measurements_thread = MeasurementsThread(
    #         socket,
    #         response_address,
    #         mpu9250,
    #         **measurement_thread_kwargs,
    #     )
    #
    #     return measurements_thread

    @staticmethod
    def time_sync(time_sync_source):
        print('Synchronizing time')
        os.system('sudo ntpdate ' + time_sync_source)

    def run(self):
        measurements_thread = None
        measurements_threads_folders = []


        time_sync_source = 'ntp1.stratum1.ru'
        state = 'idle'
        msg_num_last = None

        while True:
            # time.sleep(1)
            # msg = '1'
            # UDP_PORT = 61070
            # # UDP_IP = "192.168.1.236"
            # UDP_IP = "255.255.255.255"

            # self.status_thread.send("4", (UDP_IP, UDP_PORT))
            # print(i, time.time())
            # time.sleep(0.1)
            msg, addr = self.socket.recvfrom(1024)  # buffer size is 1024 bytes # чекнуть какой таймаут
            msg = msg.decode()
            print("received message:", msg)
            print("sender:", addr)
            # sender_ip = addr[0]
            # response_address = (sender_ip, self.UDP_PORT_SEND)

            # continue

            msg_parts = msg.split(',')
            try:
                msg_num = int(msg_parts[0])
            except :
                print("Can't parse msg '" + msg + "'")
                continue

            # TODO: add acknownledgement responses
            if msg_num == 1:  # Reset
                ack_response_num = str(msg_num) if msg_num != msg_num_last else '0'
                for _ in range(1):
                    self.acknowledgement_thread.send(ack_response_num + ',' + __version__)

                if (measurements_thread is not None) and measurements_thread.is_alive():
                    self.stop_measurements(measurements_thread)

                measurements_thread = None
                self.status_thread.periodic_sending = False
                self.time_thread.periodic_sending = True  # Changed to TRUE on 4 July
                # self.time_thread.periodic_sending = False
                self.package_num = 0

                time_sync_source = 'ntp1.stratum1.ru'
                state = 'idle'
            elif msg_num == 2:  # Start
                ack_response_num = str(msg_num) if msg_num != msg_num_last else '0'
                for _ in range(1):
                    time.sleep(0.050)
                    self.acknowledgement_thread.send(ack_response_num)

                if (measurements_thread is not None) and measurements_thread.is_alive():
                    # self.stop_measurements(measurements_thread)  ### IMPORTANT COMMENT. UNCOMMENT IF YOU WANT A SEPARATE FILE FOR EACH START
                    continue

                measurements_thread = MeasurementsThread(
                    self.sockets['client']['data'],  # It should be 'data' socket, right?  # Also should be simplified
                    self.addresses['server']['data'],
                    # ('255.255.255.255', 63070),
                    # self.sockets['client']['data'],  # It should be 'data' socket, right?  # Also should be simplified
                    # self.addresses['server']['data'],
                    self.mpu9250,
                    self.ftp_thread,
                    # **self.measurement_thread_kwargs,
                    self.measurement_thread_kwargs,
                    package_num=self.package_num,
                )
                # measurements_thread = self.get_measurements_thread(
                #     socket=self.socket,
                #     response_address=self.addresses['server']['data'],
                #     mpu9250=self.mpu9250,
                #     measurement_thread_kwargs=self.measurement_thread_kwargs,
                # )
                # measurements_thread.stop = False
                # measurements_thread = get_measurements_thread()
                measurements_thread.start()
                self.status_thread.periodic_sending = True
                state = 'measuring'
                measurements_threads_folders.append(measurements_thread.folder)
                print('I am measuring')
            elif msg_num == 3:  # Stop
                ack_response_num = str(msg_num) if msg_num != msg_num_last else '0'
                for _ in range(1):
                    time.sleep(0.100)
                    self.acknowledgement_thread.send(ack_response_num)

                self.stop_measurements(measurements_thread)
                self.status_thread.periodic_sending = False
                state = 'idle'
            elif msg_num == 4:  # Time sync
                ack_response_num = str(msg_num) if msg_num != msg_num_last else '0'
                for _ in range(1):
                    self.acknowledgement_thread.send(ack_response_num + ',0')
                # print(self.acknowledgement_thread)

                thread = Thread(target=self.time_sync, args=(time_sync_source, ))
                thread.start()
            elif msg_num == 5:  # Time sync source
                ack_response_num = str(msg_num) if msg_num != msg_num_last else '0'
                for _ in range(1):
                    self.acknowledgement_thread.send(ack_response_num)

                if len(msg_parts) >= 2:
                    new_time_sync_source = msg_parts[1]
                    try:
                        time_sync_source = str(new_time_sync_source)
                    except:
                        print('Fail to set the new time_sync_source')
            elif msg_num == 6:  # Start time sending  # Looks like it's deprecated now
                ack_response_num = str(msg_num) if msg_num != msg_num_last else '0'
                for _ in range(1):
                    self.acknowledgement_thread.send(ack_response_num)

                self.time_thread.periodic_sending = True

                # Double check because of name
            elif msg_num == 7:  # State
                ack_response_num = str(msg_num) if msg_num != msg_num_last else '0'
                for _ in range(1):
                    self.acknowledgement_thread.send(ack_response_num + ',' + state)
            elif msg_num == 8:  # Send last measurement data
                ack_response_num = str(msg_num) if msg_num != msg_num_last else '0'
                for _ in range(1):
                    self.acknowledgement_thread.send(ack_response_num)

                # TODO: add try/except
                ftp_ip = msg_parts[1]  # ftp_ip = '192.168.1.100'
                # session_ftp = FTP('192.168.1.100', 'ADMIN', 'aaa')

                for measurements_threads_folder in measurements_threads_folders:
                    folder = measurements_threads_folder

                    # session.login('ADMIN', 'aaa')
                    if folder is not None:
                        # os.listdir()
                        full_path = '/home/pi/data/' + folder + '/'
                        df_total = get_df_total(folder=full_path)  # TODO: ENABLE IT
                        ### df to bytes
                        path2save = '/home/pi/tmp/current_df.csv'
                        df_total.to_csv(path2save, index=False)

                        # file_prefix = folder[:19].replace(':', '-')
                        file_prefix = time_format2timefile_format(folder)
                        ftp_filename = 'chair__' + file_prefix + '.csv'

                        session_ftp = FTP(ftp_ip, self.player_id, self.player_id)
                        send_via_ftp(session_ftp, path2save, ftp_filename)
                        session_ftp.quit()
                    else:
                        print('measurements_thread_entity.folder is None. We need a file in a folder to send via FTP')
                else:
                    measurements_threads_folders = []



            elif msg_num == 9:  # Looks like it's deprecated now
                ack_response_num = str(msg_num) if msg_num != msg_num_last else '0'
                for _ in range(1):
                    self.acknowledgement_thread.send(ack_response_num)

                if len(msg_parts) != 3:
                    print('Incorrect number of parts: ' + str(len(msg_parts)))
                    continue

                ip_server_new = msg_parts[1]
                player_id_new = msg_parts[2]

                ports, addresses, sockets = get_ports_adresses_sockets(channels_dict, '07', player_id_new, ip_server_new, get_server_sockets=False, get_client_sockets=False)

                self.status_thread.opponent_address = addresses['server']['status']
                self.time_thread.opponent_address = addresses['server']['time']
                self.acknowledgement_thread.opponent_address = addresses['server']['ack']

                if measurements_thread is not None:
                    # measurements_thread.socket = sockets['client']
                    measurements_thread.response_address = addresses['server']['data']

                self.addresses = addresses
                print('ip and player_id are updated to ' + ip_server_new + ' , ' + player_id_new)
                # self.sockets = sockets
                # self.socket = sockets['client']['cmd']

                # get_socket(ip_server, ports['server'][channel_name])  # Add for client too


            msg_num_last = msg_num
