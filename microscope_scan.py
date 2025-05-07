# microscope_scan.py
# This is a modified version of the original code to be used as a module

import time
import csv
import matplotlib.pyplot as plt
from stellarnet_driverLibs import stellarnet_driver3 as sn
from enum import Enum
import ctypes
from ctypes import cdll, c_char_p, c_int, pointer, c_uint32
import numpy as np

# Load DLL file for PDXC2 control
KinesisDir = r"D:\Kinesis"  # Update this path if necessary
DllFile = "D:\Kinesis\Thorlabs.MotionControl.Benchtop.Piezo.dll"
lib = cdll.LoadLibrary(DllFile)
lib.TLI_InitializeSimulations()

# Device Serial Numbers
SerialNum1 = c_char_p(b"112472285")
SerialNum2 = c_char_p(b"112455201")

# Position Pointer
Position = c_int(1)
PositionPointer = pointer(Position)

class ControlMode(Enum):
    PZ_OpenLoop = 1
    PZ_CloseLoop = 2

class PDXC2_ClosedLoopParameters(ctypes.Structure):
    _fields_ = [
            ("RefSpeed"      , c_uint32  ),
            ("Proportional"  , c_uint32  ),
            ("Integral"      , c_uint32  ),
            ("Differential"  , c_uint32  ),
            ("Acceleration"  , c_uint32  ),          
            ]

def EnableDevice(serialnum):
    if lib.TLI_BuildDeviceList() == 0:
        ret = lib.PDXC2_Open(serialnum)
        print(f'PDXC2_Open Returned {ret}')
        if ret == 0:
            lib.PDXC2_Enable(serialnum)
            print('Device Enabled')
            return 0
        else:
            print('No Device Detected')
            return 1
    else:
        print('No Device Detected')
        return 1

def ClosedLoopSetMoveParamsSet(serialnum, refspeed, proportional, integral, differential, acceleration):
    ClosedLoopMoveParamsSet = PDXC2_ClosedLoopParameters(
        c_uint32(refspeed), c_uint32(proportional), c_uint32(integral), c_uint32(differential), c_uint32(acceleration)
    )
    lib.PDXC2_SetClosedLoopParams(serialnum, ClosedLoopMoveParamsSet)

def Set2ClosedLoopMode(serialnum):
    CtrlMode = ControlMode.PZ_CloseLoop.value
    lib.PDXC2_SetPositionControlMode(serialnum, CtrlMode)
    print("Set the operation mode to closed loop mode")

def GetPosition(serialnum):
    lib.PDXC2_RequestPosition(serialnum)
    lib.PDXC2_GetPosition(serialnum, PositionPointer)
    return Position.value

def SetTargetPosition(serialnum, target_position):
    lib.PDXC2_SetClosedLoopTarget(serialnum, c_int(target_position))
    lib.PDXC2_MoveStart(serialnum)

def wait_for_parallel_move(serialnum_x, target_x, serialnum_y, target_y, tolerance=50, timeout=10):
    start_time = time.time()
    while True:
        current_x = GetPosition(serialnum_x)
        current_y = GetPosition(serialnum_y)
        dx = abs(current_x - target_x)
        dy = abs(current_y - target_y)

        if dx < tolerance and dy < tolerance:
            break

        if time.time() - start_time > timeout:
            print(f"Timeout waiting for devices: X diff={dx}, Y diff={dy}")
            break
        time.sleep(0.1)

def move_pdxc2_parallel(serialnum_x, serialnum_y, target_x_nm, target_y_nm):
    SetTargetPosition(serialnum_x, target_x_nm)
    SetTargetPosition(serialnum_y, target_y_nm)
    wait_for_parallel_move(serialnum_x, target_x_nm, serialnum_y, target_y_nm)

def move_to_initial_position(initial_x_nm, initial_y_nm):
    print(f"Moving to initial start position: X = {initial_x_nm} nm, Y = {initial_y_nm} nm")
    move_pdxc2_parallel(SerialNum1, SerialNum2, initial_x_nm, initial_y_nm)
    print("Initial position reached.")

def Home(serial_num):
    print("Start Home/Zero Operation")
    lib.PDXC2_Home(serial_num)
    time.sleep(2)
    print("Home/Zero Operation Finished")

INTEGRATION_TIME = 100
SCANS_TO_AVERAGE = 1
SMOOTHING = 0
XTIMING = 3

GRID_SIZE = 51
GRID_SPACING_NM = 100000

def generate_snake_order(grid_size):
    order = []
    for row in range(1, grid_size + 1):
        cols = range(1, grid_size + 1) if row % 2 == 1 else range(grid_size, 0, -1)
        for col in cols:
            order.append((row, col))
    return order

def integrate_spectrum(wavelengths, intensities):
    return np.trapz(intensities, wavelengths)

def collect_spectrometer_data_with_plot(spectrometer, wavelengths, live_plot_ax):
    actual_x = GetPosition(SerialNum1)
    actual_y = GetPosition(SerialNum2)
    print(f"Collecting spectrum data at actual position X = {actual_x} nm, Y = {actual_y} nm")

    spectrum_data = sn.array_spectrum(spectrometer, wavelengths)
    wavelengths_list = np.array([w for w, _ in spectrum_data])
    intensities_list = np.array([i for _, i in spectrum_data])
    total_intensity = integrate_spectrum(wavelengths_list, intensities_list)

    # Clear and plot new spectrum data
    live_plot_ax.clear()
    live_plot_ax.plot(wavelengths_list, intensities_list)
    live_plot_ax.set_xlabel("Wavelength (nm)")
    live_plot_ax.set_ylabel("Intensity")
    live_plot_ax.set_title(f"Spectrum at X={actual_x}, Y={actual_y}")

    # Force redraw for live update
    live_plot_ax.figure.canvas.draw()
    live_plot_ax.figure.canvas.flush_events()
    plt.pause(0.1)

    # Save spectrum data as CSV
    filename = f"Spectrum_X{actual_x}_Y{actual_y}.csv"
    with open(filename, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Wavelength (nm)", "Intensity"])
        for wavelength, intensity in spectrum_data:
            writer.writerow([wavelength, intensity])

    return total_intensity

# The main function is kept for reference but will not be called automatically
# Instead, our Flask app will use the functions defined above
def main():
    initial_x_start = -2500000
    initial_y_start = -2500000

    Home(SerialNum1)
    Home(SerialNum2)

    EnableDevice(SerialNum1)
    EnableDevice(SerialNum2)

    Set2ClosedLoopMode(SerialNum1)
    Set2ClosedLoopMode(SerialNum2)

    ClosedLoopSetMoveParamsSet(SerialNum1, 10000000, 8192, 8192, 0, 50000000)
    ClosedLoopSetMoveParamsSet(SerialNum2, 10000000, 8192, 8192, 0, 50000000)

    move_to_initial_position(initial_x_start, initial_y_start)

    spectrometer, wavelengths = sn.array_get_spec(0)
    sn.setParam(spectrometer, INTEGRATION_TIME, SCANS_TO_AVERAGE, SMOOTHING, XTIMING, True)

    intensity_grid = np.zeros((GRID_SIZE, GRID_SIZE))
    snake_order = generate_snake_order(GRID_SIZE)

    plt.ion()
    fig, (ax_grid, ax_live) = plt.subplots(1, 2, figsize=(12, 6))
    grid_img = ax_grid.imshow(intensity_grid, cmap="hot", origin="lower")
    ax_grid.set_title("Intensity Map")
    plt.colorbar(grid_img, ax=ax_grid, label="Integrated Intensity")

    for row, col in snake_order:
        x_pos = initial_x_start + (col - 1) * GRID_SPACING_NM
        y_pos = initial_y_start + (row - 1) * GRID_SPACING_NM
        move_pdxc2_parallel(SerialNum1, SerialNum2, x_pos, y_pos)

        intensity = collect_spectrometer_data_with_plot(spectrometer, wavelengths, ax_live)
        intensity_grid[row - 1, col - 1] = intensity

        grid_img.set_data(intensity_grid)
        grid_img.autoscale()
        fig.canvas.draw()
        fig.canvas.flush_events()

    sn.reset(spectrometer)
    plt.ioff()

    # Save final heat map as an image
    plt.figure(figsize=(6, 6))
    plt.imshow(intensity_grid, cmap="hot", origin="lower")
    plt.title("Final Integrated Intensity Heat Map")
    plt.colorbar(label="Integrated Intensity")
    plt.savefig("Final_Intensity_Heatmap.png", dpi=300)
    plt.show()

if __name__ == "__main__":
    main()