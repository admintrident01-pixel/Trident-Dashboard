import unittest
import timesheets
from core import Problem

class LunchTests(unittest.TestCase):
    def sheet(self, **day):
        return {'technician':'Test tech','signature':'Test tech','weekStart':'2027-02-01','days':[{'status':'Work','method':'direct','hours':0,**day}]+[{'status':'Work','method':'direct','hours':0} for _ in range(6)]}
    def save(self, **day):
        return timesheets.save({},self.sheet(**day))[1]
    def test_direct_hours_and_saved_deduction(self):
        row=self.save(hours=8,unpaidLunch=True)
        self.assertEqual(row['total'],7.5)
        self.assertEqual(row['days'][0]['enteredHours'],8)
        self.assertEqual(row['days'][0]['lunchHours'],0.5)
    def test_times_and_unchecked(self):
        self.assertEqual(self.save(method='times',start='07:30',finish='16:00',unpaidLunch=True)['total'],8)
        self.assertEqual(self.save(method='times',start='07:30',finish='16:00',unpaidLunch=False)['total'],8.5)
    def test_zero_short_and_legacy(self):
        self.assertEqual(self.save(hours=0,unpaidLunch=True)['total'],0)
        self.assertEqual(self.save(hours=0.25,unpaidLunch=True)['total'],0)
        self.assertEqual(self.save(hours=8)['total'],8)
    def test_invalid_lunch_and_leave(self):
        with self.assertRaises(Problem):self.save(hours=8,unpaidLunch='true')
        with self.assertRaises(Problem):self.save(status='Annual leave',hours=0,unpaidLunch=True)
        self.assertEqual(self.save(status='Annual leave',hours=0,unpaidLunch=False)['total'],0)
