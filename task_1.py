import sqlite3


class Student:
    def __init__(self, first_name, last_name, middle_name, group, grades, student_id=None):
        self.id = student_id
        self.first_name = first_name
        self.last_name = last_name
        self.middle_name = middle_name
        self.group = group
        if len(grades) != 4:
            raise ValueError("Оценок должно быть ровно 4")
        self.grades = grades

    def average_grade(self):
        return sum(self.grades) / len(self.grades)


def create_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT,
            middle_name TEXT,
            group_name TEXT,
            grade1 INTEGER,
            grade2 INTEGER,
            grade3 INTEGER,
            grade4 INTEGER
        )
    ''')
    conn.commit()


def add_student(conn, student):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO students (first_name, last_name, middle_name, group_name, grade1, grade2, grade3, grade4)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student.first_name, student.last_name, student.middle_name, student.group, *student.grades))
    conn.commit()
    student.id = cursor.lastrowid
    print(f"Студент добавлен с ID {student.id}")


def get_all_students(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students")
    rows = cursor.fetchall()
    students = []
    for row in rows:
        s = Student(row[1], row[2], row[3], row[4], list(row[5:9]), row[0])
        students.append(s)
    return students


def get_student_by_id(conn, student_id):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE id=?", (student_id,))
    row = cursor.fetchone()
    if row:
        return Student(row[1], row[2], row[3], row[4], list(row[5:9]), row[0])
    return None


def update_student(conn, student):
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE students
        SET first_name=?, last_name=?, middle_name=?, group_name=?, grade1=?, grade2=?, grade3=?, grade4=?
        WHERE id=?
    ''', (*[student.first_name, student.last_name, student.middle_name, student.group, *student.grades], student.id))
    conn.commit()
    print("Данные студента обновлены.")


def delete_student(conn, student_id):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE id=?", (student_id,))
    conn.commit()
    print("Студент удалён.")


def average_grade_by_group(conn, group_name):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT grade1, grade2, grade3, grade4 FROM students WHERE group_name=?
    ''', (group_name,))
    grades_list = cursor.fetchall()
    if not grades_list:
        print("Студентов в этой группе нет.")
        return None
    averages = [sum(grades)/4 for grades in grades_list]
    group_avg = sum(averages) / len(averages)
    return group_avg


def input_grades():
    grades = []
    for i in range(4):
        while True:
            try:
                grade = int(input(f"Введите оценку {i+1} (целое число): "))
                if 1 <= grade <= 10:
                    grades.append(grade)
                    break
                else:
                    print("Оценка должна быть от 1 до 10.")
            except ValueError:
                print("Ошибка, введите целое число.")
    return grades


def main():
    conn = sqlite3.connect("resourse/students.db")
    create_table(conn)
    while True:
        print("\nМеню:")
        print("1 - Добавить студента")
        print("2 - Показать всех студентов")
        print("3 - Показать студента по ID")
        print("4 - Редактировать студента")
        print("5 - Удалить студента")
        print("6 - Средний балл по группе")
        print("7 - Выйти")

        choice = input("Выберите действие: ").strip()
        if choice == "1":
            first_name = input("Имя: ").strip()
            last_name = input("Фамилия: ").strip()
            middle_name = input("Отчество: ").strip()
            group = input("Группа: ").strip()
            grades = input_grades()
            student = Student(first_name, last_name, middle_name, group, grades)
            add_student(conn, student)

        elif choice == "2":
            students = get_all_students(conn)
            if not students:
                print("Студенты не найдены.")
            else:
                for s in students:
                    print(f"ID: {s.id} | {s.last_name} {s.first_name} {s.middle_name} | Группа: {s.group} | Оценки: {s.grades}")

        elif choice == "3":
            try:
                student_id = int(input("Введите ID студента: "))
                s = get_student_by_id(conn, student_id)
                if s:
                    print(f"{s.last_name} {s.first_name} {s.middle_name} | Группа: {s.group}")
                    print(f"Оценки: {s.grades} | Средний балл: {s.average_grade():.2f}")
                else:
                    print("Студент с таким ID не найден.")
            except ValueError:
                print("Ошибка: ID должен быть числом.")

        elif choice == "4":
            try:
                student_id = int(input("Введите ID студента для редактирования: "))
                s = get_student_by_id(conn, student_id)
                if not s:
                    print("Студент с таким ID не найден.")
                    continue
                print("Введите новые данные (оставьте пустым для пропуска):")
                new_first_name = input(f"Имя [{s.first_name}]: ").strip()
                new_last_name = input(f"Фамилия [{s.last_name}]: ").strip()
                new_middle_name = input(f"Отчество [{s.middle_name}]: ").strip()
                new_group = input(f"Группа [{s.group}]: ").strip()
                print("Введите новые оценки:")
                new_grades = []
                for i, grade in enumerate(s.grades, start=1):
                    val = input(f"Оценка {i} [{grade}]: ").strip()
                    if val == "":
                        new_grades.append(grade)
                    else:
                        try:
                            g = int(val)
                            if 1 <= g <= 10:
                                new_grades.append(g)
                            else:
                                print("Оценка вне диапазона, оставлено старое значение")
                                new_grades.append(grade)
                        except ValueError:
                            print("Ошибка ввода, оставлено старое значение")
                            new_grades.append(grade)
                if new_first_name:
                    s.first_name = new_first_name
                if new_last_name:
                    s.last_name = new_last_name
                if new_middle_name:
                    s.middle_name = new_middle_name
                if new_group:
                    s.group = new_group
                s.grades = new_grades
                update_student(conn, s)
            except ValueError:
                print("Ошибка: ID должен быть числом.")

        elif choice == "5":
            try:
                student_id = int(input("Введите ID студента для удаления: "))
                s = get_student_by_id(conn, student_id)
                if not s:
                    print("Студент с таким ID не найден.")
                    continue
                delete_student(conn, student_id)
            except ValueError:
                print("Ошибка: ID должен быть числом.")

        elif choice == "6":
            group = input("Введите название группы: ").strip()
            avg = average_grade_by_group(conn, group)
            if avg is not None:
                print(f"Средний балл по группе '{group}': {avg:.2f}")

        elif choice == "7":
            print("Выход из программы.")
            break

        else:
            print("Неверный выбор, попробуйте ещё раз.")

    conn.close()


if __name__ == "__main__":
    main()