import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os
import requests
import sqlite3

URL = "https://www.cbr-xml-daily.ru/daily_json.js"
DB_FILE = "resourse/currency_groups.db"

def load_exchange_rates():
    try:
        response = requests.get(URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data['Valute']
    except Exception as e:
        messagebox.showerror("Ошибка", f"Ошибка загрузки курсов валют:\n{e}")
        return {}

class DBHelper:
    def __init__(self, db_file=DB_FILE):
        self.conn = sqlite3.connect(db_file)
        self.create_tables()

    def create_tables(self):
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS group_currencies (
                group_id INTEGER,
                currency_code TEXT,
                PRIMARY KEY (group_id, currency_code),
                FOREIGN KEY (group_id) REFERENCES groups(id)
            )
        ''')
        self.conn.commit()

    def get_groups(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, name FROM groups ORDER BY name")
        groups_data = cur.fetchall()
        groups = {}
        for gid, name in groups_data:
            cur.execute("SELECT currency_code FROM group_currencies WHERE group_id=?", (gid,))
            codes = [row[0] for row in cur.fetchall()]
            groups[name] = codes
        return groups

    def add_group(self, group_name):
        cur = self.conn.cursor()
        try:
            cur.execute("INSERT INTO groups (name) VALUES (?)", (group_name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_group(self, group_name):
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM groups WHERE name=?", (group_name,))
        row = cur.fetchone()
        if row:
            gid = row[0]
            cur.execute("DELETE FROM group_currencies WHERE group_id=?", (gid,))
            cur.execute("DELETE FROM groups WHERE id=?", (gid,))
            self.conn.commit()
            return True
        return False

    def add_currency_to_group(self, group_name, currency_code):
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM groups WHERE name=?", (group_name,))
        row = cur.fetchone()
        if not row:
            return False
        gid = row[0]
        try:
            cur.execute("INSERT INTO group_currencies (group_id, currency_code) VALUES (?, ?)", (gid, currency_code))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_currency_from_group(self, group_name, currency_code):
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM groups WHERE name=?", (group_name,))
        row = cur.fetchone()
        if not row:
            return False
        gid = row[0]
        cur.execute("DELETE FROM group_currencies WHERE group_id=? AND currency_code=?", (gid, currency_code))
        self.conn.commit()
        return True

    def close(self):
        self.conn.close()


class CurrencyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Менеджер курсов валют ЦБ РФ")
        self.geometry("700x500")
        self.valutes = {}
        self.dbhelper = DBHelper()
        self.groups = {}
        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        tab_control = ttk.Notebook(self)
        self.tab_rates = ttk.Frame(tab_control)
        tab_control.add(self.tab_rates, text="Курсы валют")
        self.tab_groups = ttk.Frame(tab_control)
        tab_control.add(self.tab_groups, text="Группы валют")
        tab_control.pack(expand=1, fill='both')

        self.valutes_list = tk.Listbox(self.tab_rates, font=("Courier New", 12))
        scrollbar_rates = tk.Scrollbar(self.tab_rates, orient="vertical", command=self.valutes_list.yview)
        self.valutes_list.config(yscrollcommand=scrollbar_rates.set)
        self.valutes_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        scrollbar_rates.pack(side=tk.LEFT, fill=tk.Y, pady=10)

        right_frame = tk.Frame(self.tab_rates)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        tk.Label(right_frame, text="Поиск валюты по коду:", font=("Arial", 14)).pack(anchor='nw')
        self.code_entry = tk.Entry(right_frame, font=("Arial", 14))
        self.code_entry.pack(fill=tk.X, pady=5)
        self.code_entry.bind("<Return>", lambda e: self.show_currency())
        self.search_result = tk.Label(right_frame, text="", font=("Arial", 12), fg="blue")
        self.search_result.pack(anchor='nw', pady=5)
        search_btn = tk.Button(right_frame, text="Показать", command=self.show_currency)
        search_btn.pack(anchor='nw')
        refresh_btn = tk.Button(right_frame, text="Обновить курсы", command=self.refresh_courses)
        refresh_btn.pack(anchor='nw', pady=20)

        frame_groups = tk.Frame(self.tab_groups)
        frame_groups.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        group_frame = tk.Frame(frame_groups)
        group_frame.pack(side=tk.LEFT, fill=tk.Y, pady=5)
        tk.Label(group_frame, text="Группы валют:", font=("Arial", 14)).pack(anchor='nw')
        self.group_listbox = tk.Listbox(group_frame, width=30, font=("Arial", 12))
        self.group_listbox.pack(fill=tk.Y, expand=True)
        self.group_listbox.bind("<<ListboxSelect>>", self.on_group_select)
        create_group_btn = tk.Button(group_frame, text="Создать группу", command=self.create_group)
        create_group_btn.pack(pady=5, fill=tk.X)

        right_group_frame = tk.Frame(frame_groups)
        right_group_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        tk.Label(right_group_frame, text="Валюты в группе:", font=("Arial", 14)).pack(anchor='nw')
        self.currency_listbox = tk.Listbox(right_group_frame, font=("Courier New", 12))
        self.currency_listbox.pack(fill=tk.BOTH, expand=True)

        btn_frame = tk.Frame(right_group_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        add_btn = tk.Button(btn_frame, text="Добавить валюту", command=self.add_currency_to_group)
        add_btn.pack(side=tk.LEFT, padx=5)
        remove_btn = tk.Button(btn_frame, text="Удалить валюту", command=self.remove_currency_from_group)
        remove_btn.pack(side=tk.LEFT, padx=5)

        load_btn = tk.Button(btn_frame, text="Загрузить группы", command=self.load_groups_from_db)
        load_btn.pack(side=tk.RIGHT, padx=5)

    def load_data(self):
        self.valutes = load_exchange_rates()
        self.groups = self.dbhelper.get_groups()
        self.refresh_valutes_list()
        self.refresh_groups_list()

    def refresh_courses(self):
        self.valutes = load_exchange_rates()
        self.refresh_valutes_list()
        messagebox.showinfo("Обновлено", "Курсы валют обновлены.")

    def refresh_valutes_list(self):
        self.valutes_list.delete(0, tk.END)
        if not self.valutes:
            self.valutes_list.insert(tk.END, "Нет данных по валютам.")
            return
        for code, info in sorted(self.valutes.items()):
            line = f"{code}: {info['Name']} - {info['Value']} RUB"
            self.valutes_list.insert(tk.END, line)

    def show_currency(self):
        code = self.code_entry.get().strip().upper()
        if not code:
            self.search_result.config(text="Введите код валюты!")
            return
        val = self.valutes.get(code)
        if val:
            text = f"{code}: {val['Name']} - {val['Value']} RUB"
        else:
            text = "Валюта с таким кодом не найдена."
        self.search_result.config(text=text)

    def refresh_groups_list(self):
        self.group_listbox.delete(0, tk.END)
        if not self.groups:
            self.group_listbox.insert(tk.END, "Группы не созданы.")
        else:
            for group_name in sorted(self.groups.keys()):
                self.group_listbox.insert(tk.END, group_name)
        self.currency_listbox.delete(0, tk.END)

    def on_group_select(self, event):
        selection = event.widget.curselection()
        if not selection:
            return
        group_name = event.widget.get(selection[0])
        if group_name == "Группы не созданы.":
            self.currency_listbox.delete(0, tk.END)
            return
        currencies = self.groups.get(group_name, [])
        self.currency_listbox.delete(0, tk.END)
        for code in currencies:
            info = self.valutes.get(code)
            name = info['Name'] if info else ""
            self.currency_listbox.insert(tk.END, f"{code}: {name}")

    def create_group(self):
        group_name = simpledialog.askstring("Создать группу", "Введите имя новой группы:")
        if group_name:
            group_name = group_name.strip()
            if not group_name:
                messagebox.showwarning("Внимание", "Имя группы не может быть пустым.")
                return
            if group_name in self.groups:
                messagebox.showwarning("Внимание", "Группа с таким именем уже существует.")
                return
            if self.dbhelper.add_group(group_name):
                self.groups = self.dbhelper.get_groups()
                self.refresh_groups_list()
                messagebox.showinfo("Создано", f"Группа '{group_name}' успешно создана.")
            else:
                messagebox.showerror("Ошибка", "Не удалось создать группу.")

    def add_currency_to_group(self):
        selection = self.group_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Сначала выберите группу.")
            return
        group_name = self.group_listbox.get(selection[0])
        if group_name == "Группы не созданы.":
            messagebox.showwarning("Внимание", "Создайте группу сначала.")
            return
        currency_code = simpledialog.askstring("Добавить валюту", "Введите код валюты для добавления:")
        if not currency_code:
            return
        currency_code = currency_code.strip().upper()
        if currency_code not in self.valutes:
            messagebox.showerror("Ошибка", "Такой валюты нет в курсе.")
            return
        if currency_code in self.groups.get(group_name, []):
            messagebox.showinfo("Информация", "Валюта уже в группе.")
            return
        if self.dbhelper.add_currency_to_group(group_name, currency_code):
            self.groups = self.dbhelper.get_groups()
            self.on_group_select(event=tk.Event(widget=self.group_listbox))
            messagebox.showinfo("Добавлено", f"Валюта {currency_code} добавлена в группу '{group_name}'.")
        else:
            messagebox.showerror("Ошибка", "Не удалось добавить валюту в группу.")

    def remove_currency_from_group(self):
        group_sel = self.group_listbox.curselection()
        currency_sel = self.currency_listbox.curselection()
        if not group_sel or not currency_sel:
            messagebox.showwarning("Внимание", "Выберите группу и валюту для удаления.")
            return
        group_name = self.group_listbox.get(group_sel[0])
        currency_text = self.currency_listbox.get(currency_sel[0])
        currency_code = currency_text.split(":")[0]
        if group_name in self.groups and currency_code in self.groups[group_name]:
            if self.dbhelper.remove_currency_from_group(group_name, currency_code):
                self.groups = self.dbhelper.get_groups()
                self.on_group_select(event=tk.Event(widget=self.group_listbox))
                messagebox.showinfo("Удалено", f"Валюта {currency_code} удалена из группы '{group_name}'.")
            else:
                messagebox.showerror("Ошибка", "Не удалось удалить валюту из группы.")
        else:
            messagebox.showerror("Ошибка", "Валюта или группа не найдены.")

    def load_groups_from_db(self):
        self.groups = self.dbhelper.get_groups()
        self.refresh_groups_list()
        messagebox.showinfo("Загружено", "Группы загружены из базы данных.")

    def on_closing(self):
        self.dbhelper.close()
        self.destroy()

if __name__ == "__main__":
    app = CurrencyApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()