from src.scrappers.InstagramScrapper import InstagramScrapper

scrapper = InstagramScrapper("foor.rm", "RomeroMantilla12")

def main():
    scrapper.login()

    scrapper.get_follower_list()

    scrapper.get_following_list()
    



if __name__ == "__main__":
    main()
