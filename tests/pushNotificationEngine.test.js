import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { saveSubscription, removeSubscription, sendNotification } from '../src/lib/pushNotificationEngine.js';
import { db } from '../src/lib/db.js';
import webpush from 'web-push';

vi.mock('web-push', () => {
  return {
    default: {
      setVapidDetails: vi.fn(),
      sendNotification: vi.fn().mockResolvedValue({}),
      generateVAPIDKeys: vi.fn().mockReturnValue({ publicKey: "test-pub", privateKey: "test-priv" })
    }
  };
});

describe('Push Notification Engine', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Clear out testing records if any exist
    try {
      db.prepare("DELETE FROM push_subscriptions WHERE endpoint LIKE '%test.endpoint%'").run();
    } catch(e) {}
  });

  afterEach(() => {
    try {
      db.prepare("DELETE FROM push_subscriptions WHERE endpoint LIKE '%test.endpoint%'").run();
    } catch(e) {}
  });

  it('should save a new subscription successfully', () => {
    const userId = 'usr_guest_01';
    const subscription = {
      endpoint: 'https://updates.push.services.mozilla.com/wpush/v2/test_endpoint_1',
      keys: {
        p256dh: 'test_p256dh_key',
        auth: 'test_auth_key'
      }
    };

    const result = saveSubscription(userId, subscription);
    expect(result).toBe(true);

    const saved = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").get(userId);
    expect(saved).toBeDefined();
    expect(saved.endpoint).toBe(subscription.endpoint);
    expect(saved.keysP).toBe(subscription.keys.p256dh);
  });

  it('should remove a subscription successfully', () => {
    const userId = 'usr_guest_01';
    const subscription = {
      endpoint: 'https://test.endpoint/test_user_2',
      keys: {
        p256dh: 'test_p256dh_key',
        auth: 'test_auth_key'
      }
    };

    saveSubscription(userId, subscription);

    // Ensure it exists
    let saved = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").get(userId);
    expect(saved).toBeDefined();

    const result = removeSubscription(userId);
    expect(result).toBe(true);

    // Verify it's deleted
    saved = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").get(userId);
    expect(saved).toBeUndefined();
  });

  it('should send a notification using webpush', async () => {
    const userId = 'usr_guest_01';
    const subscription = {
      endpoint: 'https://test.endpoint/test_user_3',
      keys: {
        p256dh: 'test_p256dh_key',
        auth: 'test_auth_key'
      }
    };

    saveSubscription(userId, subscription);

    const payload = { title: 'Test Title', body: 'Test Body' };

    await sendNotification(userId, payload);

    expect(webpush.sendNotification).toHaveBeenCalledTimes(1);

    // The first argument should match the subscription we saved
    const calledWithSub = webpush.sendNotification.mock.calls[0][0];
    const calledWithPayload = webpush.sendNotification.mock.calls[0][1];

    expect(calledWithSub.endpoint).toBe(subscription.endpoint);
    expect(calledWithSub.keys.p256dh).toBe(subscription.keys.p256dh);
    expect(JSON.parse(calledWithPayload)).toEqual(payload);
  });
});
