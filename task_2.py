import sqlite3


class Database:
    def __init__(self, db_name="idrink.db"):
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def create_tables(self):
        cur = self.conn.cursor()

        cur.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            type TEXT CHECK(type IN ('drink', 'ingredient')),
            alcohol_strength REAL DEFAULT 0,  -- % алкоголя, 0 если безалкогольный ингридиент
            price REAL,
            stock REAL DEFAULT 0  -- количество в литрах
        )
        ''')

        cur.execute('''
        CREATE TABLE IF NOT EXISTS cocktails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            price REAL,
            strength REAL  -- Крепость коктейля (процент)
        )
        ''')

        cur.execute('''
        CREATE TABLE IF NOT EXISTS cocktail_ingredients (
            cocktail_id INTEGER,
            product_id INTEGER,
            quantity REAL,  -- в литрах
            FOREIGN KEY(cocktail_id) REFERENCES cocktails(id),
            FOREIGN KEY(product_id) REFERENCES products(id),
            PRIMARY KEY(cocktail_id, product_id)
        )
        ''')

        self.conn.commit()

    def add_product(self, name, ptype, strength, price, stock):
        cur = self.conn.cursor()
        try:
            cur.execute('''
                INSERT INTO products (name, type, alcohol_strength, price, stock)
                VALUES (?,?,?,?,?)
            ''', (name, ptype, strength, price, stock))
            self.conn.commit()
            print(f"{ptype.title()} '{name}' добавлен.")
        except sqlite3.IntegrityError:
            print("Ошибка: продукт с таким названием уже существует.")

    def restock_product(self, name, amount):
        cur = self.conn.cursor()
        cur.execute('SELECT stock FROM products WHERE name=?', (name,))
        row = cur.fetchone()
        if not row:
            print("Продукт не найден.")
            return
        new_stock = row[0] + amount
        cur.execute('UPDATE products SET stock=? WHERE name=?', (new_stock, name))
        self.conn.commit()
        print(f"Запасы '{name}' обновлены. Новый остаток: {new_stock:.2f} л.")

    def list_products(self):
        cur = self.conn.cursor()
        cur.execute('SELECT name, type, alcohol_strength, price, stock FROM products')
        for row in cur.fetchall():
            print(f"{row[0]} ({row[1]}), крепость: {row[2]}%, цена: {row[3]:.2f}, остаток: {row[4]:.2f} л")

    def add_cocktail(self, name, ingredients_with_quantities):
        """
        ingredients_with_quantities - список кортежей (product_name, количество в литрах)
        """

        cur = self.conn.cursor()
        product_ids = []
        recipe_ratio = 0
        total_strength = 0
        total_price = 0

        for prod_name, qty in ingredients_with_quantities:
            cur.execute('SELECT id, alcohol_strength, price, stock FROM products WHERE name=?', (prod_name,))
            product = cur.fetchone()
            if not product:
                print(f"Продукт '{prod_name}' не найден, коктейль не создан.")
                return
            if product[3] < qty:
                print(f"Недостаточно '{prod_name}' на складе. Нужно {qty} л, осталось {product[3]:.2f} л.")
                return
            product_ids.append((product[0], qty))
            recipe_ratio += qty
            total_strength += (product[1] * qty)
            total_price += (product[2] * qty)

        strength = total_strength / recipe_ratio if recipe_ratio > 0 else 0
        cocktail_price = total_price * 1.5

        try:
            cur.execute("INSERT INTO cocktails (name, price, strength) VALUES (?, ?, ?)", (name, cocktail_price, strength))
            cocktail_id = cur.lastrowid
            for pid, qty in product_ids:
                cur.execute("INSERT INTO cocktail_ingredients (cocktail_id, product_id, quantity) VALUES (?, ?, ?)", (cocktail_id, pid, qty))
            self.conn.commit()
            print(f"Коктейль '{name}' добавлен c ценой {cocktail_price:.2f} и крепостью {strength:.2f}%.")
        except sqlite3.IntegrityError:
            print("Ошибка: коктейль с таким названием уже существует.")

    def list_cocktails(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, name, price, strength FROM cocktails")
        cocktails = cur.fetchall()
        if not cocktails:
            print("Коктейлей пока нет.")
            return
        for c in cocktails:
            print(f"[{c[0]}] {c[1]}, цена: {c[2]:.2f}, крепость: {c[3]:.2f}%")
            cur.execute("""
                SELECT p.name, ci.quantity FROM cocktail_ingredients ci
                JOIN products p ON ci.product_id = p.id
                WHERE ci.cocktail_id = ?
            """, (c[0],))
            ingredients = cur.fetchall()
            for ing in ingredients:
                print(f"   - {ing[0]} : {ing[1]:.2f} л")

    def sell(self, name, amount=1):
        cur = self.conn.cursor()

        cur.execute("SELECT id, type, alcohol_strength, price, stock FROM products WHERE name=?", (name,))
        product = cur.fetchone()
        if product:
            if product[4] < amount:
                print(f"Недостаточно продукта '{name}'. Остаток: {product[4]:.2f} л")
                return
            new_stock = product[4] - amount
            cur.execute("UPDATE products SET stock=? WHERE id=?", (new_stock, product[0]))
            self.conn.commit()
            print(f"Продано {amount:.2f} л '{name}'. Остаток на складе: {new_stock:.2f} л.")
            return

        cur.execute("SELECT id, price FROM cocktails WHERE name=?", (name,))
        cocktail = cur.fetchone()
        if cocktail:
            cocktail_id = cocktail[0]
            cur.execute("""
                SELECT product_id, quantity FROM cocktail_ingredients WHERE cocktail_id=?
            """, (cocktail_id,))
            ingredients = cur.fetchall()
            for pid, qty in ingredients:
                cur.execute("SELECT stock, name FROM products WHERE id=?", (pid,))
                stock, prod_name = cur.fetchone()
                required_qty = qty * amount
                if stock < required_qty:
                    print(f"Недостаточно ингредиента '{prod_name}' для приготовления коктейля '{name}'. Не хватает {required_qty - stock:.2f} л.")
                    return
            for pid, qty in ingredients:
                cur.execute("SELECT stock FROM products WHERE id=?", (pid,))
                stock = cur.fetchone()[0]
                new_stock = stock - qty * amount
                cur.execute("UPDATE products SET stock=? WHERE id=?", (new_stock, pid))
            self.conn.commit()
            print(f"Продано {amount} шт. коктейля '{name}'.")
            return

        print("Продукт или коктейль не найден.")

    def close(self):
        self.conn.close()


def main():
    db = Database()

    while True:
        print("\nМеню:")
        print("1 - Добавить напиток/ингредиент")
        print("2 - Пополнить запасы")
        print("3 - Просмотреть товары на складе")
        print("4 - Добавить коктейль")
        print("5 - Просмотреть коктейли")
        print("6 - Продать напиток или коктейль")
        print("7 - Выход")
        choice = input("Выберите действие: ").strip()

        if choice == "1":
            name = input("Название напитка/ингредиента: ").strip()
            ptype = input("Тип (drink/ingredient): ").strip()
            if ptype not in ("drink", "ingredient"):
                print("Ошибка: тип должен быть 'drink' или 'ingredient'")
                continue
            strength = 0
            if ptype == "drink":
                try:
                    strength = float(input("Крепость алкоголя (%): ").strip())
                except ValueError:
                    print("Ошибка: введите число")
                    continue
            try:
                price = float(input("Цена за литр: ").strip())
                stock = float(input("Начальный остаток (л): ").strip())
            except ValueError:
                print("Ошибка: введите число")
                continue
            db.add_product(name, ptype, strength, price, stock)

        elif choice == "2":
            name = input("Название напитка/ингредиента для пополнения: ").strip()
            try:
                amount = float(input("Количество (литры): ").strip())
                if amount <= 0:
                    raise ValueError
            except ValueError:
                print("Ошибка: введите положительное число")
                continue
            db.restock_product(name, amount)

        elif choice == "3":
            print("Склад:")
            db.list_products()

        elif choice == "4":
            cocktail_name = input("Название коктейля: ").strip()
            print("Введите состав коктейля. Для окончания ввода оставьте название пустым.")
            ingredients = []
            while True:
                prod_name = input("Название ингредиента/напитка: ").strip()
                if not prod_name:
                    break
                try:
                    qty = float(input("Количество (литры): ").strip())
                except ValueError:
                    print("Ошибка: введите число")
                    continue
                ingredients.append((prod_name, qty))
            if not ingredients:
                print("Коктейль без ингредиентов не может быть добавлен.")
                continue
            db.add_cocktail(cocktail_name, ingredients)

        elif choice == "5":
            print("Коктейли:")
            db.list_cocktails()

        elif choice == "6":
            name = input("Название напитка или коктейля для продажи: ").strip()
            try:
                amount = float(input("Количество (литры или шт): ").strip())
                if amount <= 0:
                    raise ValueError
            except ValueError:
                print("Ошибка: введите положительное число")
                continue
            db.sell(name, amount)

        elif choice == "7":
            print("Выход.")
            db.close()
            break
        else:
            print("Неверный выбор. Попробуйте снова.")


if __name__ == "__main__":
    main()