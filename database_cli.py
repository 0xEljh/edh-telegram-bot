import sqlite3
from prettytable import PrettyTable


def run_query(db_path, query):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        results = cursor.fetchall()

        # Display results in table format
        table = PrettyTable()
        table.field_names = [desc[0] for desc in cursor.description]
        table.add_rows(results)
        print(table)

    except sqlite3.Error as e:
        print(f"Error: {str(e)}")
    finally:
        conn.close()


if __name__ == "__main__":
    # db_path = input("Database path: ")
    db_path = "data/games.db"
    while True:
        query = input("\nSQL> ")
        if query.lower() in ("exit", "quit"):
            break
        run_query(db_path, query)
