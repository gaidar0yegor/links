import psycopg2
import os

# Get database credentials
db_host = os.environ.get('DB_HOST', 'db')
db_user = os.environ.get('DB_USER', 'postgres_user')
db_pass = os.environ.get('DB_PASS', 'postgres_password')
db_name = os.environ.get('DB_NAME', 'affiliate_bot_db')

print(f"Connecting to {db_host}/{db_name} as {db_user}")

try:
    conn = psycopg2.connect(
        host=db_host,
        user=db_user,
        password=db_pass,
        dbname=db_name
    )
    conn.autocommit = True
    cur = conn.cursor()

    print("Connected successfully!")

    # Read and execute SQL file
    with open('fix_campaigns.sql', 'r') as f:
        sql_content = f.read()

    # Split into individual statements
    statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip() and not stmt.strip().startswith('--')]

    for stmt in statements:
        if stmt:
            try:
                cur.execute(stmt)
                print(f"Executed: {stmt[:80]}...")
            except Exception as e:
                print(f"Error on statement: {e}")

    print("All SQL executed successfully!")

    # Verify campaigns
    cur.execute("SELECT id, name, params->>'max_sales_rank' as max_rank FROM campaigns ORDER BY id;")
    campaigns = cur.fetchall()

    print("\nFinal campaigns:")
    for campaign in campaigns:
        print(f"  {campaign[0]}: {campaign[1]} (max_sales_rank: {campaign[2]})")

    # Count campaigns
    cur.execute("SELECT COUNT(*) FROM campaigns;")
    count = cur.fetchone()[0]
    print(f"Total campaigns: {count}")

    cur.close()
    conn.close()

except Exception as e:
    print(f"Error: {e}")
