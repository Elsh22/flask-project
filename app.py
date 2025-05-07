# app.py
from flask import Flask, render_template, jsonify, request, send_file
import threading
import time
import numpy as np
import io
import base64
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import random
import os

app = Flask(__name__)

# Global variables to track scan state
scan_running = False
scan_thread = None
current_progress = {"row": 0, "col": 0, "total": 0, "percentage": 0}
status_messages = ["Ready to start scanning..."]
spectrum_image = None
grid_image = None
current_position = {"x": 0, "y": 0}

# Timestamps for when the images were last updated
last_spectrum_update = 0
last_grid_update = 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_scan', methods=['POST'])
def start_scan():
    global scan_running, scan_thread
    
    if scan_running:
        return jsonify({"status": "error", "message": "Scan already running"})
    
    scan_running = True
    scan_thread = threading.Thread(target=run_scan)
    scan_thread.daemon = True
    scan_thread.start()
    
    return jsonify({"status": "success", "message": "Scan started"})

@app.route('/stop_scan', methods=['POST'])
def stop_scan():
    global scan_running
    if scan_running:
        scan_running = False
        return jsonify({"status": "success", "message": "Scan stopping..."})
    else:
        return jsonify({"status": "error", "message": "No scan running"})

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        "running": scan_running,
        "messages": status_messages[-10:],  # Return last 10 messages
        "progress": current_progress,
        "position": current_position,
        "spectrum_timestamp": last_spectrum_update,
        "grid_timestamp": last_grid_update
    })

@app.route('/spectrum_image')
def get_spectrum_image():
    global spectrum_image
    
    # Check if there's a timestamp in the request for cache busting
    request_timestamp = request.args.get('t', '')
    
    if spectrum_image is None:
        # Return a blank image if no data yet
        fig = plt.figure(figsize=(6, 4))
        plt.text(0.5, 0.5, "No data yet", ha='center', va='center')
        plt.gca().set_axis_off()
        
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png')
        plt.close(fig)
        img_buf.seek(0)
        
        response = send_file(img_buf, mimetype='image/png')
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    
    # Add cache control headers to prevent caching
    response = send_file(spectrum_image, mimetype='image/png')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/grid_image')
def get_grid_image():
    global grid_image
    
    # Check if there's a timestamp in the request for cache busting
    request_timestamp = request.args.get('t', '')
    
    if grid_image is None:
        # Return a blank image if no data yet
        fig = plt.figure(figsize=(6, 6))
        plt.text(0.5, 0.5, "No data yet", ha='center', va='center')
        plt.gca().set_axis_off()
        
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png')
        plt.close(fig)
        img_buf.seek(0)
        
        response = send_file(img_buf, mimetype='image/png')
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    
    # Add cache control headers to prevent caching
    response = send_file(grid_image, mimetype='image/png')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

def add_status_message(message):
    global status_messages
    timestamp = time.strftime("%H:%M:%S")
    status_messages.append(f"[{timestamp}] {message}")
    print(f"[{timestamp}] {message}")

# Simulate spectrum data
def generate_simulated_spectrum():
    wavelengths = np.linspace(400, 800, 1000)
    intensities = 100 * np.exp(-(wavelengths - 550)**2 / 1000) + 20 * np.exp(-(wavelengths - 650)**2 / 500) + np.random.random(1000) * 10
    return wavelengths, intensities

def create_spectrum_plot(wavelengths, intensities, x_pos, y_pos):
    global spectrum_image, last_spectrum_update
    
    fig = plt.figure(figsize=(6, 4))
    plt.plot(wavelengths, intensities)
    plt.xlabel("Wavelength (nm)")
    plt.ylabel("Intensity")
    plt.title(f"Spectrum at X={x_pos}, Y={y_pos}")
    
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=100)
    plt.close(fig)
    img_buf.seek(0)
    
    spectrum_image = img_buf
    last_spectrum_update = int(time.time() * 1000)  # Current time in milliseconds
    
    return img_buf

def create_grid_plot(intensity_grid):
    global grid_image, last_grid_update
    
    fig = plt.figure(figsize=(6, 6))
    plt.imshow(intensity_grid, cmap="hot", origin="lower")
    plt.title("Integrated Intensity Heat Map")
    plt.colorbar(label="Integrated Intensity")
    
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=100)
    plt.close(fig)
    img_buf.seek(0)
    
    grid_image = img_buf
    last_grid_update = int(time.time() * 1000)  # Current time in milliseconds
    
    return img_buf

def run_scan():
    global scan_running, current_progress, current_position
    
    try:
        # Initialize simulation parameters
        grid_size = 10  # Smaller grid for faster simulation
        intensity_grid = np.zeros((grid_size, grid_size))
        current_progress["total"] = grid_size * grid_size
        
        # Generate snake scan pattern
        snake_order = []
        for row in range(1, grid_size + 1):
            cols = range(1, grid_size + 1) if row % 2 == 1 else range(grid_size, 0, -1)
            for col in cols:
                snake_order.append((row, col))
        
        # Emit initial status
        add_status_message('Initializing scan...')
        time.sleep(1)  # Simulate initialization time
        
        # Loop through grid positions
        for idx, (row, col) in enumerate(snake_order):
            if not scan_running:
                add_status_message('Scan stopped by user.')
                break
                
            # Update progress
            current_progress["row"] = row
            current_progress["col"] = col
            current_progress["percentage"] = int((idx + 1) / len(snake_order) * 100)
            
            # Simulate movement to position
            add_status_message(f'Moving to position {idx+1}/{len(snake_order)}: Row {row}, Col {col}')
            time.sleep(0.5)  # Simulate movement time
            
            # Simulate current position coordinates
            x_pos = -2500000 + (col - 1) * 100000
            y_pos = -2500000 + (row - 1) * 100000
            current_position["x"] = x_pos
            current_position["y"] = y_pos
            
            # Simulate collecting spectrum
            add_status_message(f'Collecting spectrum data at position {idx+1}/{len(snake_order)}')
            time.sleep(0.5)  # Simulate data collection time
            
            # Generate simulated spectrum data
            wavelengths, intensities = generate_simulated_spectrum()
            
            # Calculate simulated intensity (using integrated area under curve)
            intensity = np.trapz(intensities, wavelengths)
            
            # Update intensity grid
            intensity_grid[row - 1, col - 1] = intensity
            
            # Create and save plots
            create_spectrum_plot(wavelengths, intensities, x_pos, y_pos)
            create_grid_plot(intensity_grid)
            
            time.sleep(1.0)  # Simulated delay between measurements
        
        if scan_running:
            # Create final heat map
            create_grid_plot(intensity_grid)
            add_status_message('Scan completed successfully')
            
            # Save final heat map as a file
            plt.figure(figsize=(8, 8))
            plt.imshow(intensity_grid, cmap="hot", origin="lower")
            plt.title("Final Integrated Intensity Heat Map")
            plt.colorbar(label="Integrated Intensity")
            plt.savefig("Final_Intensity_Heatmap.png", dpi=300)
            plt.close()
            
            add_status_message('Final heat map saved as "Final_Intensity_Heatmap.png"')
    
    except Exception as e:
        add_status_message(f'Error during scan: {str(e)}')
    
    finally:
        scan_running = False

if __name__ == '__main__':
    app.run(debug=True)