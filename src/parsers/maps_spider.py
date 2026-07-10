from typing import List
import logging
import requests
import json
from contact_parser.src.configs.settings import config
import polars as pl

logger = logging.getLogger("terra_doc.twogisparser")

class TwoGisAPIParser:
    def __init__(self):
        self.db_path = config.SQLITE_DB_PATH

        self.regions = (pl.read_csv('regions.csv')
                        .filter(pl.col("region").is_in(["Москва", "Московская область", "Санкт-Петербург"]))
                        .select(pl.col('id'), pl.col("region")))
        
        self.rubrics = pl.read_json('rubrics.json').select(pl.col("id"), pl.col("name"))
        self.__2gis_api_key: str = config.TWO_GIS_API_KEY

    def parse_to_json(self, rubric_id: int, region_id: int, pages: List[int] | int):
        api_url = f"https://catalog.api.2gis.com/3.0/items?rubric_id={rubric_id}&region_id={region_id}&page_size=50&page={pages}&key={self.__2gis_api_key}"
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json().get("result", {}).get("items", [])
            with open("C:/dev/parser/contact_parser/maps_data/results/results.jsonl", "a", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
                print("Done")

        else:
            print(f"Ошибка получения регионов: {response.status_code}")
            return 



    def search_urls(self, url):
        pass