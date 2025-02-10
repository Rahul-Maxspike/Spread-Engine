import logging
import requests
import tkinter as tk
from datetime import datetime
# for TermLogger
from termcolor import colored

import constants
import path_config


class CustomLogger:
    def __init__(self, filename):
        self.logger = logging.getLogger('custom_logger')
        self.logger.setLevel(logging.DEBUG)
        self.filename = filename
        self.term_logger = TermLogger()

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        file_handler = logging.FileHandler(path_config.APPLICATION_LOG_PATH)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def log(self, level, message):
        filename = self.filename
        # Include filename in the log message
        message_with_filename = f"{filename} - {message}"

        if level == 'debug':
            self.logger.debug(message_with_filename)
        elif level == 'info':
            self.logger.info(message_with_filename)
        elif level == 'warning':
            self.logger.warning(message_with_filename)
        elif level == 'error':
            self.logger.error(message_with_filename)
            self.term_logger.print_colored(message_with_filename, 'red', attrs=['bold', 'reverse'])
        elif level == 'critical':
            self.logger.critical(message_with_filename)
        else:
            print("Invalid log level")




class TermLogger:
    def __init__(self):
        pass  # No initialization needed for now

    def print_order_details(self, instrument, is_an_add, order_type, theta, qty_total, atm_level, option_type, order_caller):
        """
        Prints the order details in a formatted and colored way.
        
        :param instrument: The instrument number.
        :param order_caller: The string that identifies who called the order.
        :param is_an_add: Boolean indicating whether it's an additional order.
        :param order_type: The type of the order (e.g., 'sell', 'buy').
        :param theta: The theta value.
        """
        date_time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output = (
            f"{colored(date_time_now, 'grey')} - "
            f"Placing order for instrument {colored(instrument, 'cyan', attrs=['bold'])}, "
            f"is_an_add: {colored(is_an_add, 'magenta', attrs=['bold'])}, "
            f"order_type: {colored(order_type, 'red', attrs=['bold'])}, "
            f"theta: {colored(theta, 'green', attrs=['bold'])}, "
            f"qty_total: {colored(qty_total, 'yellow', attrs=['bold'])}, "
            f"atm_level: {colored(atm_level, 'blue', attrs=['bold'])}, "
            f"option_type: {colored(option_type, 'magenta', attrs=['bold'])}, "
            f"called by {colored(order_caller, 'yellow', attrs=['bold'])}"
        )
        
        print(output)
    
    def print_df(self, df, title, color):
        """
        Prints the DataFrame in a formatted and colored way.
        
        :param df: The DataFrame to print.
        :param title: The title of the DataFrame.
        :param color: The color to use for the title.
        """
        # print(f"colored(title, color, attrs=['bold'])") center the title
        print(colored(title.center(60, '-'), color))
        print(colored(df, color))
        print(colored('-' * 60, color))

    def print_colored(self, message, color, attrs=[]):
        """
        Prints the message in the specified color.
        
        :param message: The message to print.
        :param color: The color to use.
        """
        print(colored(message, color, attrs=attrs))

# Telegram Bot Messenger

class TelegramBot:
    def __init__(self):
        self.token = constants.TELEGRAM_BOT_TOKEN
        self.chat_id = constants.TRENDLINES_CHAT_ID

    def send_message(self, message):
        try:
            url=f"https://api.telegram.org/bot{self.token}/sendMessage?chat_id={self.chat_id}&text={message}"
            if not requests.get(url).json()['ok']:
                raise Exception("Failed to send message on Telegram")
        except Exception as e:
            print(e)


# Confirmation Popup

class ConfirmationPopup:
    def __init__(self, root, message, title="Confirmation"):
        self.root = root
        self.message = message
        self.title = title
        self.popup = None
        self.result = None

    def show(self):
        # Create the pop-up window
        self.popup = tk.Toplevel(self.root)
        self.popup.title(self.title)

        # Set up the message
        label = tk.Label(self.popup, text=self.message)
        label.pack(pady=20)

        # Set up the buttons
        yes_button = tk.Button(self.popup, text="Yes", command=self.yes_action)
        yes_button.pack(side="left", padx=20, pady=20)

        no_button = tk.Button(self.popup, text="No", command=self.no_action)
        no_button.pack(side="right", padx=20, pady=20)

        # Center the popup on the screen
        self.popup.geometry("300x150+%d+%d" % (self.root.winfo_screenwidth() / 2 - 150, self.root.winfo_screenheight() / 2 - 75))

        # Start the Tkinter main loop, which will block further code execution until the window is closed
        self.root.mainloop()
        return self.result

    def yes_action(self):
        self.result = "Yes"
        print("You clicked Yes!")
        self.popup.destroy()
        self.root.quit()

    def no_action(self):
        self.result = "No"
        print("You clicked No!")
        self.popup.destroy()
        self.root.quit()
    
    # function to close the popup
    def close_popup(self):
        self.popup.destroy()
        self.root.quit()