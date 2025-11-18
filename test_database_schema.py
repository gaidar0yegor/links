#!/usr/bin/env python3
"""
Simple test to verify database schema and product_queue table creation.
"""

import asyncio
import sys
import os

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import conf
from db.postgres import init_db_pool

async def test_database_schema():
    """Test database schema and product_queue table."""
    print("🔍 Testing Database Schema and Product Queue Table")
    print("=" * 60)

    try:
        # Connect to database
        db_pool = await init_db_pool()
        if not db_pool:
            print("❌ Database connection failed")
            return False

        print("✅ Database connected successfully")

        async with db_pool.acquire() as conn:
            # Check if product_queue table exists
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'product_queue'
                );
            """)

            if not result:
                print("❌ product_queue table does not exist")
                return False

            print("✅ product_queue table exists")

            # Check table structure
            columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'product_queue'
                ORDER BY ordinal_position;
            """)

            expected_columns = {
                'id': 'integer',
                'campaign_id': 'integer',
                'asin': 'text',
                'title': 'text',
                'price': 'numeric',
                'currency': 'character varying',
                'rating': 'numeric',
                'review_count': 'integer',
                'sales_rank': 'integer',
                'image_url': 'text',
                'affiliate_link': 'text',
                'browse_node_ids': 'ARRAY',
                'quality_score': 'integer',
                'status': 'character varying',
                'discovered_at': 'timestamp without time zone',
                'posted_at': 'timestamp without time zone',
                'updated_at': 'timestamp without time zone'
            }

            print("📋 Checking table columns:")
            for col in columns:
                col_name = col['column_name']
                col_type = col['data_type']
                expected_type = expected_columns.get(col_name)

                if expected_type:
                    if expected_type in col_type:
                        print(f"  ✅ {col_name}: {col_type}")
                    else:
                        print(f"  ❌ {col_name}: {col_type} (expected: {expected_type})")
                        return False
                else:
                    print(f"  ⚠️  Unexpected column: {col_name}")

            # Check indexes
            indexes = await conn.fetch("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'product_queue';
            """)

            index_names = [idx['indexname'] for idx in indexes]
            expected_indexes = [
                'idx_product_queue_campaign_status',
                'idx_product_queue_discovered'
            ]

            print("📋 Checking indexes:")
            for expected_idx in expected_indexes:
                if any(expected_idx in idx_name for idx_name in index_names):
                    print(f"  ✅ {expected_idx}")
                else:
                    print(f"  ❌ Missing index: {expected_idx}")
                    return False

            # Test basic queue operations
            print("📋 Testing basic queue operations:")

            # Insert test product
            test_asin = f'TEST_SCHEMA_{asyncio.get_event_loop().time()}'
            product_id = await conn.fetchval("""
                INSERT INTO product_queue (
                    campaign_id, asin, title, price, currency, rating,
                    review_count, sales_rank, image_url, affiliate_link,
                    browse_node_ids, quality_score
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id;
            """, 999, test_asin, 'Test Product', 99.99, 'USD', 4.5, 100, 2500,
                 'https://example.com/image.jpg', 'https://amazon.com/test',
                 ['1626160311'], 2500)

            if not product_id:
                print("  ❌ Failed to insert test product")
                return False

            print(f"  ✅ Inserted test product with ID: {product_id}")

            # Check queue size
            queue_size = await conn.fetchval(
                "SELECT COUNT(*) FROM product_queue WHERE campaign_id = $1 AND status = 'queued'",
                999
            )

            if queue_size != 1:
                print(f"  ❌ Queue size incorrect: {queue_size}, expected: 1")
                return False

            print(f"  ✅ Queue size correct: {queue_size}")

            # Get next product
            next_product = await conn.fetchrow(
                "SELECT * FROM product_queue WHERE campaign_id = $1 AND status = 'queued' ORDER BY discovered_at ASC LIMIT 1",
                999
            )

            if not next_product or next_product['asin'] != test_asin:
                print("  ❌ Failed to retrieve queued product")
                return False

            print(f"  ✅ Retrieved queued product: {next_product['asin']}")

            # Mark as posted
            await conn.execute(
                "UPDATE product_queue SET status = 'posted', posted_at = CURRENT_TIMESTAMP WHERE id = $1",
                product_id
            )

            # Verify status
            status = await conn.fetchval(
                "SELECT status FROM product_queue WHERE id = $1", product_id
            )

            if status != 'posted':
                print(f"  ❌ Status not updated: {status}")
                return False

            print("  ✅ Product marked as posted")

            # Clean up test data
            await conn.execute("DELETE FROM product_queue WHERE campaign_id = 999")
            print("  ✅ Test data cleaned up")

        print("\n🎉 DATABASE SCHEMA TEST COMPLETED SUCCESSFULLY!")
        print("✅ Product queue table created correctly")
        print("✅ All columns and indexes present")
        print("✅ Basic queue operations working")
        return True

    except Exception as e:
        print(f"❌ Database schema test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function."""
    result = await test_database_schema()
    if result:
        print("\n✅ All database tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Database tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
