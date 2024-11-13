from datetime import datetime
import time
import traceback
import prawcore

# 1200 seconds == 20 min
def call_function_repeatedly(function, pauze_seconds = 1200):
    while True:
        try:
            start_time = datetime.now()
            print(f"Starting function execution at: {start_time}")
            
            function()
            
            end_time = datetime.now()
            print(f"Function execution completed at: {end_time}")
            
            execution_time = end_time - start_time
            print(f"Function execution took: {execution_time}\n")
        except prawcore.exceptions.TooManyRequests as e:
            print("Rate limit exceeded. Waiting 10 minutes before retrying...")
            print(f"Error message: {str(e)}")
            print("\nFull traceback:")
            traceback.print_exc()
            time.sleep(600)
            continue
        except Exception as e:
            print(f"Error message: {str(e)}")
            print("\nFull traceback:")
            traceback.print_exc()
        
        time.sleep(pauze_seconds)