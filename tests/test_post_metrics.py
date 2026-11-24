"""Regression: monitored cards must read captured reactions, not legacy zeros."""
import unittest
from types import SimpleNamespace
from app.services.meta_posts import post_metric_values


class PostMetricTests(unittest.TestCase):
    def post(self, **values):
        return SimpleNamespace(**({'likes_count': 0, 'views_count': 0, 'shares_count': 0} | values))

    def snapshot(self, **values):
        return SimpleNamespace(**({'likes_count': 21, 'reactions_count': 40, 'shares_count': None,
                                   'status': 'available', 'updated_at': None, 'detail': 'Captured'} | values))

    def test_capture_overrides_old_zero_and_keeps_like_distinct_from_total(self):
        result = post_metric_values(self.post(), self.snapshot())
        self.assertEqual(result['reactions_count'], 40)
        self.assertEqual(result['likes_count'], 21)

    def test_unavailable_counts_are_not_reported_as_zero(self):
        result = post_metric_values(self.post(), None)
        for key in ('likes_count', 'reactions_count', 'views_count', 'shares_count'):
            self.assertIsNone(result[key])

    def test_confirmed_zero_remains_zero(self):
        result = post_metric_values(self.post(likes_count=123), self.snapshot(likes_count=0, reactions_count=0, shares_count=0))
        for key in ('likes_count', 'reactions_count', 'shares_count'):
            self.assertEqual(result[key], 0)

    def test_retained_capture_and_partial_status_remain_visible(self):
        result = post_metric_values(self.post(), self.snapshot(status='partial'))
        self.assertEqual(result['reactions_count'], 40)
        self.assertEqual(result['metrics_status'], 'partial')

    def test_legacy_like_count_is_never_used_as_total_reactions(self):
        result = post_metric_values(self.post(likes_count=19), None)
        self.assertEqual(result['likes_count'], 19)
        self.assertIsNone(result['reactions_count'])
