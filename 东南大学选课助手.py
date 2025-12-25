import os
import sys
import time
import subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

# Configuration
class Config:
    ELEC_TURN = os.getenv('ELEC_TURN', '1')  # Default to turn 1 if not set
    MAX_RETRIES = 3
    RETRY_DELAY = 1
    CLICK_DELAY = 0.5
    WAIT_TIMEOUT = 20

class Logger:
    @staticmethod
    def info(message):
        print(f"[INFO] {message}")
    
    @staticmethod
    def error(message):
        print(f"[ERROR] {message}")
    
    @staticmethod
    def success(message):
        print(f"[SUCCESS] {message}")
    
    @staticmethod
    def warning(message):
        print(f"[WARNING] {message}")

def search_and_elect_class(driver, course_name, menu_index, button_index=0):
    """
    Reusable function to search for a course and elect it.
    
    Args:
        driver: Selenium WebDriver instance
        course_name: Name of the course to search for
        menu_index: Menu index (0=第一轮, 1=系统推荐课程, 2=第二轮, 3=第三轮, 4=第四轮, 5=第五轮)
        button_index: Index of the elect button (default: 0 for first result)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        Logger.info(f"Searching for course: {course_name} (menu_index={menu_index}, button_index={button_index})")
        
        # Step 1: Click the menu item to navigate to the correct selection turn
        menu_items = driver.find_elements(By.XPATH, "//a[@class='menu-item']")
        if menu_index >= len(menu_items):
            Logger.error(f"Menu index {menu_index} out of range. Available items: {len(menu_items)}")
            return False
        
        menu_items[menu_index].click()
        time.sleep(Config.CLICK_DELAY)
        Logger.info(f"Clicked menu item at index {menu_index}")
        
        # Step 2: Find and fill the search input field
        wait = WebDriverWait(driver, Config.WAIT_TIMEOUT)
        search_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='请输入课程名称' or @placeholder='课程名称']")))
        search_input.clear()
        search_input.send_keys(course_name)
        time.sleep(Config.CLICK_DELAY)
        Logger.info(f"Entered course name: {course_name}")
        
        # Step 3: Click the search button
        search_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), '搜索') or contains(text(), 'Search')]")))
        search_button.click()
        time.sleep(Config.CLICK_DELAY * 2)  # Wait for search results to load
        Logger.info("Search button clicked, waiting for results...")
        
        # Step 4: Wait for search results and get all elect buttons
        elect_buttons = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//button[contains(text(), '选课') or contains(text(), 'Elect')]")))
        
        if button_index >= len(elect_buttons):
            Logger.error(f"Button index {button_index} out of range. Available buttons: {len(elect_buttons)}")
            return False
        
        # Step 5: Click the specified elect button
        # Use ActionChains to handle potential stale elements
        actions = ActionChains(driver)
        actions.move_to_element(elect_buttons[button_index]).click().perform()
        time.sleep(Config.CLICK_DELAY)
        Logger.success(f"Clicked elect button at index {button_index}")
        
        # Step 6: Wait for confirmation or success message
        try:
            success_message = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '成功') or contains(text(), '选课成功')]")), Config.WAIT_TIMEOUT)
            Logger.success(f"Course {course_name} elected successfully!")
            return True
        except TimeoutException:
            Logger.warning(f"No success confirmation for course {course_name}, but election may have succeeded")
            return True
            
    except TimeoutException:
        Logger.error(f"Timeout while searching for course: {course_name}")
        return False
    except NoSuchElementException as e:
        Logger.error(f"Element not found while processing course {course_name}: {str(e)}")
        return False
    except StaleElementReferenceException:
        Logger.warning(f"Stale element reference for course {course_name}, retrying...")
        return False
    except Exception as e:
        Logger.error(f"Unexpected error while processing course {course_name}: {str(e)}")
        return False

def elect_courses(driver, courses):
    """
    Elect multiple courses using the refactored search_and_elect_class function.
    
    Args:
        driver: Selenium WebDriver instance
        courses: List of course dictionaries with keys: 'name', 'menu_index', 'button_index' (optional)
    
    Returns:
        dict: Statistics of election results
    """
    stats = {
        'total': len(courses),
        'successful': 0,
        'failed': 0,
        'failed_courses': []
    }
    
    for course in courses:
        course_name = course.get('name')
        menu_index = course.get('menu_index', 0)
        button_index = course.get('button_index', 0)
        
        if not course_name:
            Logger.warning("Course name not specified, skipping...")
            stats['failed'] += 1
            continue
        
        retries = 0
        success = False
        
        while retries < Config.MAX_RETRIES and not success:
            try:
                success = search_and_elect_class(driver, course_name, menu_index, button_index)
                if success:
                    stats['successful'] += 1
                else:
                    retries += 1
                    if retries < Config.MAX_RETRIES:
                        Logger.info(f"Retrying course {course_name} (attempt {retries + 1}/{Config.MAX_RETRIES})")
                        time.sleep(Config.RETRY_DELAY)
            except Exception as e:
                Logger.error(f"Exception during course election: {str(e)}")
                retries += 1
                if retries < Config.MAX_RETRIES:
                    time.sleep(Config.RETRY_DELAY)
        
        if not success:
            stats['failed'] += 1
            stats['failed_courses'].append(course_name)
    
    return stats

def print_election_statistics(stats):
    """Print election statistics."""
    Logger.info("=" * 50)
    Logger.info("ELECTION STATISTICS")
    Logger.info("=" * 50)
    Logger.info(f"Total courses: {stats['total']}")
    Logger.success(f"Successfully elected: {stats['successful']}")
    Logger.error(f"Failed to elect: {stats['failed']}")
    
    if stats['failed_courses']:
        Logger.warning("Failed courses:")
        for course in stats['failed_courses']:
            Logger.warning(f"  - {course}")
    
    Logger.info("=" * 50)

def main():
    """
    Main function to orchestrate the course election process.
    Supports multiple courses with all 5 menu items (turns).
    """
    Logger.info("Starting SEU Course Election Helper...")
    Logger.info(f"Election Turn (ELEC_TURN): {Config.ELEC_TURN}")
    
    # Initialize WebDriver
    try:
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless')  # Uncomment for headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(options=options)
        Logger.success("WebDriver initialized successfully")
    except Exception as e:
        Logger.error(f"Failed to initialize WebDriver: {str(e)}")
        sys.exit(1)
    
    try:
        # Navigate to the course election system
        driver.get("https://newelection.seu.edu.cn/")  # Replace with actual URL
        Logger.info("Navigating to course election system...")
        time.sleep(2)
        
        # Define courses to elect
        # Format: {'name': 'course_name', 'menu_index': 0-4, 'button_index': 0 (default)}
        # menu_index: 0=第一轮, 1=系统推荐课程(TJKC), 2=第二轮, 3=第三轮, 4=第四轮
        courses = [
            {'name': '高等数学(一)', 'menu_index': 0},  # First turn
            {'name': '数据结构', 'menu_index': 1},      # System recommendation
            {'name': '操作系统', 'menu_index': 2},      # Second turn
            {'name': '数据库原理', 'menu_index': 3},    # Third turn
            {'name': '编译原理', 'menu_index': 4},      # Fourth turn
        ]
        
        # You can also specify button_index if multiple results exist
        # {'name': 'course_name', 'menu_index': 0, 'button_index': 1}
        
        # Execute elections
        Logger.info(f"Starting election process for {len(courses)} course(s)...")
        stats = elect_courses(driver, courses)
        
        # Print results
        print_election_statistics(stats)
        
        # Keep browser open for verification (optional)
        if stats['failed'] == 0:
            Logger.success("All courses elected successfully!")
        else:
            Logger.warning(f"Some courses failed to elect. Please review the failed list.")
        
        # Uncomment below to keep browser open for debugging
        # input("Press Enter to close the browser...")
        
    except Exception as e:
        Logger.error(f"An error occurred in main execution: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()
        Logger.info("WebDriver closed")

if __name__ == "__main__":
    main()
