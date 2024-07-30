from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import IPython

class FuzztainerScraper():
    def __init__(self, image):
        if ':' not in image:
            self.image = image.strip()
        else:
            self.image =  image.split(":")[0].strip()
            self.version = image.split(":")[1].strip()

    def scrape(self):
        if len(self.image.split("/")) > 1:
            url = f"https://hub.docker.com/r/{self.image}"
        else:
            url = f"https://hub.docker.com/_/{self.image}"

        with sync_playwright() as p:
            browser = p.firefox.launch(
                headless=True, 
                args=[
                    "--no-sandbox", 
                    "--disable-setuid-sandbox", 
                    "--disable-gpu", 
                    "--disable-dev-shm-usage"
                ])
            page = browser.new_page()
            page.goto(url)
            
            try:
                #waiting for javascript to render html
                page.wait_for_load_state('networkidle')
                content = page.content()
            except:
                #wait for 2 seconds and try again
                page.wait_for_timeout(2000)
                try:
                    content = page.content()
                except:
                    return None 
                
            browser.close()

            #Searching and formatting html content into an easily readable stirng to pass into openai
            soup = BeautifulSoup(content, "html.parser")
            overview = soup.find("div", {"data-testid": "markdownContent"}) 
            description = soup.find("p", {"data-testid": "description"})
        
            result = ""

            if overview:
                result += "<overview>" + overview.text + "</overview>\n"
                
            if description:
                result +=  "<description>" + description.text + "</description>"

            if result == "":
                return None
        
            return result


            


        





