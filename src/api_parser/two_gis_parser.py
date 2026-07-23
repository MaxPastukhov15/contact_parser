import json
import logging
import requests
from typing import Optional
import polars as pl
from src.configs.settings import config, DataPaths

logger = logging.getLogger("terra_doc.twogisparser")

class TwoGisAPIParser:
    def __init__(self):
        self.db_path = config.SQLITE_DB_PATH

        logger.info("Loading regions and categories from files...")
        self.regions = (pl.read_csv(DataPaths.REGIONS_PATH)
                        .filter(pl.col("region").is_in(["Москва", "Московская область", "Санкт-Петербург"]))
                        .select(pl.col('id'))
                        .to_series().to_list())
        
        self.rubrics = pl.read_json(DataPaths.RUBRICS_PATH).select(pl.col("id")).to_series().to_list()
        self.__2gis_api_key: str = config.TWO_GIS_API_KEY
        
        logger.info(f"Uploaded regions: {len(self.regions)}, categories: {len(self.rubrics)}")

    def parse_to_json(self, rubric_id: Optional[int] = None, query: Optional[str] = None, 
                      region_id: Optional[int] = None, page: Optional[int] = 1, 
                      contacts_available: bool = True) -> None: 
        api_url = f"https://catalog.api.2gis.com/3.0/items?key={self.__2gis_api_key}&page_size=10"

        if contacts_available:
            api_url += "&fields=items.contact_groups"           
        if query:
            api_url += f"&q={query}"
        if region_id:
            api_url += f"&region_id={region_id}"
        if page:
            api_url += f"&page={page}"
        if rubric_id:
            api_url += f"&rubric_id={rubric_id}"

        print(f"Отправка запроса: {api_url}") 
        try:
            response = requests.get(api_url)
        except requests.RequestException as e:
            logger.error(f"Network error during the request: {e}")
            return

        if response.status_code == 200:
            print("OK")
            result_data = response.json().get("result", {})
            data = result_data.get("items", [])
            total_count = result_data.get("total", 0)
            
            logger.debug(f"Successfully! Companies found on the page: {len(data)} (Total by request: {total_count})")
            
            if not data:
                logger.warning(f"The {page} page returned an empty items list.")
                return

            output_file = "C:/dev/parser/contact_parser/maps_data/results/results_rubrics_id.jsonl"
            with open(output_file, "a", encoding="utf-8") as file:
                for item in data:
                    file.write(json.dumps(item, ensure_ascii=False) + "\n")
            logger.debug(f"Data has been successfully written to {output_file}")

        elif response.status_code == 404:
            logger.warning(f"No data found (404) for the region {region_id}, query: '{query}', page: {page}")
        else:
            logger.error(f"API 2GIS error: {response.status_code}. Answer: {response.text}")
            raise ValueError(f"Couldn't get any results: {response.status_code}")

    def get_items(self, number_of_pages_to_parse: int = 1)->None:
        if not self.rubrics or not self.regions:
            logger.error("The lists of categories or regions are empty! Check the input CSV/JSON files.")
            return

        for rubric in self.rubrics:
            for region in self.regions:
                for i in range(1, number_of_pages_to_parse + 1):
                    logger.info(f"Processing: Category='{rubric}', Region ID={region}, Page={i}")
                    self.parse_to_json(region_id=region, contacts_available=True, rubric_id=rubric)

