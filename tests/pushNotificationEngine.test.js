import { describe, it, expect, vi, beforeEach } from 'vitest';
import { saveSubscription, removeSubscription, sendNotification } from '../src/lib/pushNotificationEngine.js';
import { db } from '../src/lib/db.js';

// Mock web-push to avoid actual network calls
vi.mock('web-push', () => {
  return {
    default: {
      setVapidDetails: vi.fn(),
      sendNotification: vi.fn().mockResolvedValue(true)
    }
  };
});

describe('Push Notification Engine', () => {
  beforeEach(() => {
    db.prepare('DELETE FROM push_subscriptions').run();
  });

  const mockUserId = 'usr_guest_01'; // Use an existing user from INITIAL_USERS to satisfy foreign key constraint
  const mockSubscription = {
    endpoint: 'https://fcm.googleapis.com/fcm/send/test1234',
    keys: {
      p256dh: 'BNc_...',
      auth: 'A1B2...'
    }
  };

  it('should successfully save a new subscription to the database', () => {
    const result = saveSubscription(mockUserId, mockSubscription);
    expect(result.success).toBe(true);

    const subscriptions = db.prepare('SELECT * FROM push_subscriptions WHERE userId = ?').all(mockUserId);
    expect(subscriptions.length).toBe(1);
    expect(subscriptions[0].endpoint).toBe(mockSubscription.endpoint);
  });

  it('should remove a subscription from the database', () => {
    saveSubscription(mockUserId, mockSubscription);
    const result = removeSubscription(mockUserId, mockSubscription.endpoint);
    expect(result.success).toBe(true);
    expect(result.removed).toBe(1);

    const subscriptions = db.prepare('SELECT * FROM push_subscriptions WHERE userId = ?').all(mockUserId);
    expect(subscriptions.length).toBe(0);
  });

  it('should successfully send a notification to a subscribed user', async () => {
    saveSubscription(mockUserId, mockSubscription);

    const result = await sendNotification(mockUserId, {
      title: 'Test Notification',
      body: 'This is a test'
    });

    expect(result.success).toBe(true);
    expect(result.sent).toBe(1);
  });

  it('should handle sending notifications to a user with no subscriptions', async () => {
    const result = await sendNotification('usr_no_sub', {
      title: 'No Sub',
      body: 'Should not crash'
    });

    expect(result.success).toBe(false);
    expect(result.reason).toBe('No active subscriptions for user');
  });
});
