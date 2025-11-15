#!/usr/bin/env python3
"""
Posting Scheduler Service for Telegram Affiliate Bot
Handles scheduling and timing of affiliate content posts.
"""

import datetime
from typing import List, Dict, Optional, Any
from services.sheets_api import sheets_api
from services.logger import bot_logger


class PostingScheduler:
    """Service for managing posting schedules and timing."""

    def __init__(self):
        self.schedules_cache = {}
        self._load_schedules()

    def _load_schedules(self):
        """Load posting schedules from Google Sheets."""
        try:
            schedules_data = sheets_api.get_sheet_data('posting_schedules')
            if schedules_data and len(schedules_data) > 1:
                headers = schedules_data[0]
                col_indices = {header: idx for idx, header in enumerate(headers)}

                self.schedules_cache = {}
                for row in schedules_data[1:]:
                    if len(row) >= len(headers):
                        schedule_id = row[col_indices.get('schedule_id', 0)]
                        name = row[col_indices.get('name', 1)]
                        days_of_week = row[col_indices.get('days_of_week', 2)]
                        time_slots = row[col_indices.get('time_slots', 3)]
                        frequency = row[col_indices.get('frequency', 4)]

                        # Parse days of week (e.g., "1,2,3,4,5" -> [1,2,3,4,5])
                        days_list = []
                        if days_of_week:
                            try:
                                days_list = [int(d.strip()) for d in days_of_week.split(',') if d.strip().isdigit()]
                            except ValueError:
                                days_list = []

                        # Parse time slots (e.g., "08:00,09:00,10:00" -> ["08:00", "09:00", "10:00"])
                        time_list = []
                        if time_slots:
                            time_list = [t.strip() for t in time_slots.split(',') if t.strip()]

                        self.schedules_cache[schedule_id] = {
                            'id': schedule_id,
                            'name': name,
                            'days_of_week': days_list,
                            'time_slots': time_list,
                            'frequency': frequency
                        }

            bot_logger.log_info("PostingScheduler", f"Loaded {len(self.schedules_cache)} posting schedules")

        except Exception as e:
            bot_logger.log_error("PostingScheduler", e, "Failed to load posting schedules from Google Sheets")
            self.schedules_cache = {}

    def get_schedule_by_id(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific schedule by ID."""
        return self.schedules_cache.get(schedule_id)

    def get_all_schedules(self) -> Dict[str, Dict[str, Any]]:
        """Get all available schedules."""
        return self.schedules_cache.copy()

    def get_next_posting_time(self, schedule_id: str, from_time: Optional[datetime.datetime] = None) -> Optional[datetime.datetime]:
        """
        Calculate the next posting time based on the schedule.

        Args:
            schedule_id: ID of the schedule to use
            from_time: Starting time to calculate from (default: now)

        Returns:
            Next posting datetime or None if no valid schedule
        """
        if from_time is None:
            from_time = datetime.datetime.now()

        schedule = self.get_schedule_by_id(schedule_id)
        if not schedule:
            return None

        days_of_week = schedule.get('days_of_week', [])
        time_slots = schedule.get('time_slots', [])

        if not days_of_week or not time_slots:
            return None

        # Find next valid posting time
        current_time = from_time

        # Check up to 7 days ahead
        for _ in range(7):
            current_weekday = current_time.weekday() + 1  # Monday = 1, Sunday = 7

            if current_weekday in days_of_week:
                # This day is valid for posting, find next time slot
                current_date = current_time.date()

                for time_str in time_slots:
                    try:
                        # Parse time (e.g., "08:00" -> hour=8, minute=0)
                        hour, minute = map(int, time_str.split(':'))
                        post_time = datetime.datetime.combine(current_date, datetime.time(hour, minute))

                        if post_time > current_time:
                            return post_time

                    except (ValueError, AttributeError):
                        continue

            # Move to next day
            current_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)

        return None

    def get_posting_times_for_day(self, schedule_id: str, date: Optional[datetime.date] = None) -> List[datetime.datetime]:
        """
        Get all posting times for a specific day according to the schedule.

        Args:
            schedule_id: ID of the schedule to use
            date: Date to get times for (default: today)

        Returns:
            List of posting datetimes for the day
        """
        if date is None:
            date = datetime.date.today()

        schedule = self.get_schedule_by_id(schedule_id)
        if not schedule:
            return []

        days_of_week = schedule.get('days_of_week', [])
        time_slots = schedule.get('time_slots', [])

        # Check if this day is valid for posting
        weekday = date.weekday() + 1  # Monday = 1, Sunday = 7
        if weekday not in days_of_week:
            return []

        posting_times = []
        for time_str in time_slots:
            try:
                hour, minute = map(int, time_str.split(':'))
                post_time = datetime.datetime.combine(date, datetime.time(hour, minute))
                posting_times.append(post_time)
            except (ValueError, AttributeError):
                continue

        return sorted(posting_times)

    def is_time_to_post(self, schedule_id: str, current_time: Optional[datetime.datetime] = None) -> bool:
        """
        Check if it's time to post according to the schedule.

        Args:
            schedule_id: ID of the schedule to check
            current_time: Current time (default: now)

        Returns:
            True if it's time to post
        """
        if current_time is None:
            current_time = datetime.datetime.now()

        schedule = self.get_schedule_by_id(schedule_id)
        if not schedule:
            return False

        days_of_week = schedule.get('days_of_week', [])
        time_slots = schedule.get('time_slots', [])

        # Check if today is a posting day
        current_weekday = current_time.weekday() + 1
        if current_weekday not in days_of_week:
            return False

        # Check if current time matches any time slot (within 5 minutes)
        current_time_str = current_time.strftime('%H:%M')
        for time_slot in time_slots:
            try:
                # Parse the time slot
                slot_hour, slot_minute = map(int, time_slot.split(':'))
                slot_time = datetime.time(slot_hour, slot_minute)

                # Create datetime for comparison
                slot_datetime = datetime.datetime.combine(current_time.date(), slot_time)

                # Check if current time is within 5 minutes of the slot
                time_diff = abs((current_time - slot_datetime).total_seconds())
                if time_diff <= 300:  # 5 minutes in seconds
                    return True

            except (ValueError, AttributeError):
                continue

        return False

    def get_schedule_summary(self, schedule_id: str) -> Optional[str]:
        """Get a human-readable summary of a schedule."""
        schedule = self.get_schedule_by_id(schedule_id)
        if not schedule:
            return None

        name = schedule.get('name', 'Unknown')
        days = schedule.get('days_of_week', [])
        times = schedule.get('time_slots', [])

        # Convert day numbers to names
        day_names = {
            1: 'Mon', 2: 'Tue', 3: 'Wed', 4: 'Thu', 5: 'Fri', 6: 'Sat', 7: 'Sun'
        }
        day_str = ', '.join([day_names.get(d, str(d)) for d in days])

        time_str = ', '.join(times)

        return f"{name}: {day_str} at {time_str}"


# Global instance
posting_scheduler = PostingScheduler()
