import aiosqlite
from scrapy.exceptions import DropItem

class SQLitePipeline:
    def __init__(self, db_path):
        self.db_path = db_path
        self.db = None
    
    async def init_table(self):
        self.db = await aiosqlite.connect(self.db_path)
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT,
                description TEXT, category TEXT, rubric TEXT,
                email TEXT, phone TEXT,
                website_url TEXT, region TEXT,
                address TEXT, source TEXT,
                crawl_status TEXT DEFAULT 'pending',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await self.db.execute('''CREATE UNIQUE INDEX 
                IF NOT EXISTS idx_url ON organizations(website_url)''')
        await self.db.commit()
    
    async def process_item(self, item, spider):
        try:
            if self.db is not None:

                await self.db.execute('''
                    INSERT INTO organizations 
                    (company_name, description, category, rubric, email, phone, website_url, region, address, source, crawl_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(website_url) DO UPDATE SET
                    email=excluded.email,
                    phone=excluded.phone,
                    crawl_status=excluded.crawl_status,
                    updated_at=CURRENT_TIMESTAMP
                    ''', (
                item.get('company_name'), item.get('description'), item.get('category'),
                item.get('rubric'), item.get('email'), item.get('phone'),
                item.get('website_url'), item.get('region'), item.get('address'),
                item.get('source'), item.get('crawl_status', 'pending')
                ))

                await self.db.commit()
        
        except Exception as e:
            spider.logger.error(f"Ошибка записи в БД: {e}")
            raise DropItem(f"Не удалось сохранить {item.get('company_name')}")
            
        return item

    async def close_db(self):
        if self.db:
            await self.db.close()