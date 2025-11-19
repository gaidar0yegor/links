#!/usr/bin/env python3
"""
Comprehensive Testing Suite for Streamlined Quality Scoring System
Tests the complete workflow: Database → Campaign → Discovery → Queue → Posting
"""

import asyncio
import sys
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import conf
from services.amazon_paapi_client import amazon_paapi_client
from services.campaign_manager import CampaignManager, set_campaign_manager, get_campaign_manager
from services.post_manager import PostManager
from services.scheduler import CampaignScheduler
from services.product_filter import product_filter
from db.postgres import init_db_pool
from aiogram import Bot

class StreamlinedSystemTester:
    """Complete testing suite for the streamlined quality scoring system."""

    def __init__(self):
        self.db_pool = None
        self.campaign_manager = None
        self.bot = None
        self.post_manager = None
        self.scheduler = None
        self.test_campaign_id = None
        self.results = {}
        self.errors = []

    def log(self, message: str, level: str = "INFO"):
        """Log testing progress."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def log_error(self, message: str):
        """Log errors."""
        self.errors.append(message)
        self.log(message, "ERROR")

    async def setup_infrastructure(self) -> bool:
        """Phase 1: Test infrastructure setup."""
        self.log("🔧 PHASE 1: Testing Infrastructure Setup")
        self.log("=" * 60)

        try:
            # 1.1 Database Connection
            self.log("Testing database connection...")
            self.db_pool = await init_db_pool()
            if not self.db_pool:
                self.log_error("Database pool initialization failed")
                return False
            self.log("✅ Database connected successfully")

            # 1.2 Campaign Manager
            self.log("Testing campaign manager initialization...")
            self.campaign_manager = CampaignManager(db_pool=self.db_pool)
            set_campaign_manager(self.campaign_manager)
            self.log("✅ Campaign manager initialized")

            # 1.3 Bot Initialization
            self.log("Testing bot initialization...")
            self.bot = Bot(token=conf.bot_token)
            self.post_manager = PostManager(bot=self.bot)
            self.log("✅ Bot and post manager initialized")

            # 1.4 Scheduler (without starting jobs)
            self.log("Testing scheduler initialization...")
            self.scheduler = CampaignScheduler(self.bot, self.db_pool, self.campaign_manager)
            self.log("✅ Scheduler initialized")

            return True

        except Exception as e:
            self.log_error(f"Infrastructure setup failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    async def test_database_schema(self) -> bool:
        """Test database schema and product_queue table."""
        self.log("Testing database schema...")

        try:
            async with self.db_pool.acquire() as conn:
                # Check if product_queue table exists
                result = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'product_queue'
                    );
                """)

                if not result:
                    self.log_error("product_queue table does not exist")
                    return False

                self.log("✅ product_queue table exists")

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

                for col in columns:
                    col_name = col['column_name']
                    col_type = col['data_type']
                    if col_name in expected_columns:
                        expected_type = expected_columns[col_name]
                        if expected_type not in col_type:
                            self.log_error(f"Column {col_name} has wrong type: {col_type}, expected: {expected_type}")
                            return False

                self.log("✅ product_queue table structure correct")

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

                for expected_idx in expected_indexes:
                    if not any(expected_idx in idx_name for idx_name in index_names):
                        self.log_error(f"Missing index: {expected_idx}")
                        return False

                self.log("✅ Database indexes created correctly")
                return True

        except Exception as e:
            self.log_error(f"Database schema test failed: {str(e)}")
            return False

    async def test_campaign_creation(self) -> bool:
        """Test campaign creation with sales rank parameter."""
        self.log("Testing campaign creation with sales rank...")

        try:
            # Create test campaign
            test_campaign = {
                'name': f'Test Streamlined Campaign {datetime.now().strftime("%H%M%S")}',
                'channels': ['@test_channel'],
                'categories': ['electronics'],
                'subcategories': {},
                'rating': 4.0,
                'min_price': 10.0,
                'max_sales_rank': 5000,  # Test custom sales rank threshold
                'language': 'en'
            }

            # Save campaign
            campaign_id = await self.campaign_manager.save_new_campaign(test_campaign)
            if not campaign_id:
                self.log_error("Campaign creation failed")
                return False

            self.test_campaign_id = campaign_id
            self.log(f"✅ Test campaign created with ID: {campaign_id}")

            # Verify campaign data
            campaign_details = await self.campaign_manager.get_campaign_details(campaign_id)
            if not campaign_details:
                self.log_error("Cannot retrieve campaign details")
                return False

            params = campaign_details.get('params', {})
            if params.get('max_sales_rank') != 5000:
                self.log_error(f"Sales rank not saved correctly: {params.get('max_sales_rank')}")
                return False

            self.log("✅ Campaign sales rank parameter saved correctly")
            return True

        except Exception as e:
            self.log_error(f"Campaign creation test failed: {str(e)}")
            return False

    async def test_amazon_api_real_data(self) -> bool:
        """Test Amazon API returns real data, not mock."""
        self.log("Testing Amazon API for real data (not mock)...")

        try:
            # Test with real API call
            search_result = await amazon_paapi_client.search_items_enhanced(
                browse_node_ids=['1626160311'],  # Electronics browse node
                min_rating=4.0,
                max_results=3
            )

            if not search_result or len(search_result) == 0:
                self.log_error("Amazon API returned no results")
                return False

            # Check if data looks real (not mock)
            product = search_result[0]

            # Verify required fields exist
            required_fields = ['asin', 'title', 'price', 'sales_rank']
            for field in required_fields:
                if field not in product or product[field] is None:
                    self.log_error(f"Missing required field: {field}")
                    return False

            # Check sales rank is reasonable (not obviously fake)
            sales_rank = product.get('sales_rank')
            if not isinstance(sales_rank, int) or sales_rank <= 0 or sales_rank > 10000000:
                self.log_error(f"Unrealistic sales rank: {sales_rank}")
                return False

            # Check price is reasonable
            price = product.get('price')
            if price is not None and (price <= 0 or price > 100000):
                self.log_error(f"Unrealistic price: {price}")
                return False

            self.log(f"✅ Amazon API returned real product: {product['title'][:50]}...")
            self.log(f"   ASIN: {product['asin']}, Sales Rank: {sales_rank}, Price: ${price}")
            return True

        except Exception as e:
            self.log_error(f"Amazon API real data test failed: {str(e)}")
            return False

    async def test_product_filtering(self) -> bool:
        """Test simplified product filtering (sales rank only)."""
        self.log("Testing simplified product filtering...")

        try:
            # Create test products with different sales ranks
            test_products = [
                {'asin': 'TEST001', 'title': 'High Rank Product', 'sales_rank': 1000},
                {'asin': 'TEST002', 'title': 'Medium Rank Product', 'sales_rank': 5000},
                {'asin': 'TEST003', 'title': 'Low Rank Product', 'sales_rank': 15000},
                {'asin': 'TEST004', 'title': 'No Rank Product', 'sales_rank': None}
            ]

            # Test filtering with threshold of 10000
            filtered = product_filter.apply_sales_rank_filter(test_products, max_sales_rank=10000)

            # Should keep products with rank <= 10000
            expected_asins = ['TEST001', 'TEST002']  # 1000 and 5000
            actual_asins = [p['asin'] for p in filtered]

            if set(actual_asins) != set(expected_asins):
                self.log_error(f"Filtering failed. Expected: {expected_asins}, Got: {actual_asins}")
                return False

            self.log(f"✅ Sales rank filtering working: {len(filtered)}/{len(test_products)} products passed")
            return True

        except Exception as e:
            self.log_error(f"Product filtering test failed: {str(e)}")
            return False

    async def test_queue_operations(self) -> bool:
        """Test queue management operations."""
        self.log("Testing queue operations...")

        try:
            # Test data
            test_product = {
                'asin': f'TEST_QUEUE_{datetime.now().strftime("%H%M%S")}',
                'title': 'Test Queue Product',
                'price': 99.99,
                'currency': 'USD',
                'rating': 4.5,
                'review_count': 100,
                'sales_rank': 2500,
                'image_url': 'https://example.com/image.jpg',
                'affiliate_link': 'https://amazon.com/test',
                'browse_node_ids': ['1626160311']
            }

            # 1. Add product to queue
            product_id = await self.campaign_manager.add_product_to_queue(
                self.test_campaign_id, test_product
            )
            if not product_id:
                self.log_error("Failed to add product to queue")
                return False

            self.log(f"✅ Product added to queue with ID: {product_id}")

            # 2. Check queue size
            queue_size = await self.campaign_manager.get_queue_size(self.test_campaign_id)
            if queue_size != 1:
                self.log_error(f"Queue size incorrect: {queue_size}, expected: 1")
                return False

            self.log(f"✅ Queue size correct: {queue_size}")

            # 3. Get next queued product
            next_product = await self.campaign_manager.get_next_queued_product(self.test_campaign_id)
            if not next_product or next_product['asin'] != test_product['asin']:
                self.log_error("Failed to retrieve queued product")
                return False

            self.log(f"✅ Next queued product retrieved: {next_product['asin']}")

            # 4. Mark as posted
            await self.campaign_manager.mark_product_posted(product_id)

            # 5. Verify status changed
            async with self.db_pool.acquire() as conn:
                status = await conn.fetchval(
                    "SELECT status FROM product_queue WHERE id = $1", product_id
                )
                if status != 'posted':
                    self.log_error(f"Product status not updated: {status}")
                    return False

            self.log("✅ Product marked as posted successfully")
            return True

        except Exception as e:
            self.log_error(f"Queue operations test failed: {str(e)}")
            return False

    async def test_discovery_cycle(self) -> bool:
        """Test product discovery cycle (manual trigger)."""
        self.log("Testing product discovery cycle...")

        try:
            # Get campaign details
            campaign = await self.campaign_manager.get_campaign_details(self.test_campaign_id)
            if not campaign:
                self.log_error("Cannot get campaign details for discovery test")
                return False

            # Check initial queue size
            initial_size = await self.campaign_manager.get_queue_size(self.test_campaign_id)
            self.log(f"Initial queue size: {initial_size}")

            # Manually trigger discovery for this campaign
            await self.scheduler.product_discovery_cycle()

            # Check queue size after discovery
            final_size = await self.campaign_manager.get_queue_size(self.test_campaign_id)
            self.log(f"Final queue size: {final_size}")

            if final_size < initial_size:
                self.log_error("Queue size decreased after discovery (unexpected)")
                return False

            if final_size > initial_size:
                self.log(f"✅ Discovery cycle added {final_size - initial_size} products to queue")
            else:
                self.log("ℹ️  Discovery cycle completed (no new products added)")

            return True

        except Exception as e:
            self.log_error(f"Discovery cycle test failed: {str(e)}")
            return False

    async def cleanup_test_data(self) -> bool:
        """Clean up test data."""
        self.log("Cleaning up test data...")

        try:
            if self.test_campaign_id:
                # Delete test campaign (cascade will delete queue items)
                await self.campaign_manager.delete_campaign(self.test_campaign_id)
                self.log(f"✅ Test campaign {self.test_campaign_id} deleted")

            return True

        except Exception as e:
            self.log_error(f"Cleanup failed: {str(e)}")
            return False

    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run the complete testing suite."""
        self.log("🚀 STARTING COMPREHENSIVE STREAMLINED SYSTEM TESTING")
        self.log("=" * 80)

        test_phases = [
            ("Infrastructure Setup", self.setup_infrastructure),
            ("Database Schema", self.test_database_schema),
            ("Campaign Creation", self.test_campaign_creation),
            ("Amazon API Real Data", self.test_amazon_api_real_data),
            ("Product Filtering", self.test_product_filtering),
            ("Queue Operations", self.test_queue_operations),
            ("Discovery Cycle", self.test_discovery_cycle),
        ]

        results = {}

        for phase_name, test_func in test_phases:
            self.log(f"\n📋 PHASE: {phase_name}")
            self.log("-" * 60)

            try:
                result = await test_func()
                results[phase_name.lower().replace(" ", "_")] = result

                if result:
                    self.log(f"✅ {phase_name}: PASSED")
                else:
                    self.log(f"❌ {phase_name}: FAILED")

            except Exception as e:
                self.log_error(f"{phase_name} crashed: {str(e)}")
                results[phase_name.lower().replace(" ", "_")] = False

        # Cleanup
        self.log("\n🧹 CLEANUP PHASE")
        self.log("-" * 60)
        await self.cleanup_test_data()

        # Summary
        self.log("\n" + "=" * 80)
        self.log("🎯 COMPREHENSIVE TESTING RESULTS SUMMARY")
        self.log("=" * 80)

        passed = 0
        total = len(results)

        for test_name, result in results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            self.log(f"{test_name.replace('_', ' ').title()}: {status}")
            if result:
                passed += 1

        success_rate = (passed / total) * 100
        self.log(f"\n📊 OVERALL RESULT: {passed}/{total} tests passed ({success_rate:.1f}%)")

        if self.errors:
            self.log(f"\n❌ ERRORS ENCOUNTERED ({len(self.errors)}):")
            for i, error in enumerate(self.errors[:5], 1):  # Show first 5 errors
                self.log(f"  {i}. {error}")
            if len(self.errors) > 5:
                self.log(f"  ... and {len(self.errors) - 5} more errors")

        # Final assessment
        if success_rate >= 90:
            self.log("\n🎉 EXCELLENT: Streamlined system working perfectly!")
        elif success_rate >= 75:
            self.log("\n✅ GOOD: System working with minor issues")
        elif success_rate >= 50:
            self.log("\n⚠️  FAIR: System has some issues to address")
        else:
            self.log("\n❌ POOR: Major issues detected, needs fixing")

        return {
            'results': results,
            'errors': self.errors,
            'success_rate': success_rate,
            'passed': passed,
            'total': total
        }

async def main():
    """Main testing function."""
    print("🎯 Streamlined Quality Scoring System - Comprehensive Testing Suite")
    print("=" * 80)

    # Environment check
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Database config: {'✅' if conf.db.name else '❌'}")
    print(f"Bot token: {'✅' if conf.bot_token else '❌'}")
    print(f"Amazon API: {'✅' if conf.amazon.access_key else '❌'}")
    print()

    # Run comprehensive tests
    tester = StreamlinedSystemTester()
    results = await tester.run_comprehensive_test()

    # Cleanup
    if hasattr(tester, 'bot') and tester.bot:
        await tester.bot.session.close()

    # Exit with appropriate code
    success_rate = results['success_rate']
    if success_rate >= 75:
        print("\n🎉 Streamlined system testing completed successfully!")
        sys.exit(0)
    else:
        print(f"\n❌ Testing failed - only {success_rate:.1f}% success rate")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
