import { useState, useEffect, useCallback } from "react";

interface PushSubscriptionData {
  endpoint: string;
  keys: { p256dh: string; auth: string };
}

interface UsePushReturn {
  supported: boolean;
  subscribed: boolean;
  permission: NotificationPermission | "unsupported";
  subscribe: () => Promise<void>;
  unsubscribe: () => Promise<void>;
  sendTest: () => Promise<void>;
}

export function usePushNotifications(): UsePushReturn {
  const [supported, setSupported] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">("unsupported");

  useEffect(() => {
    const isSupported =
      "serviceWorker" in navigator &&
      "PushManager" in window &&
      "Notification" in window;
    setSupported(isSupported);

    if (!isSupported) return;

    setPermission(Notification.permission);

    // Check if already subscribed
    navigator.serviceWorker.ready
      .then((reg) => reg.pushManager.getSubscription())
      .then((sub) => {
        setSubscribed(sub !== null);
      })
      .catch(() => {});
  }, []);

  const subscribe = useCallback(async () => {
    if (!supported) return;

    // Request permission
    const perm = await Notification.requestPermission();
    setPermission(perm);
    if (perm !== "granted") return;

    // Register service worker
    await navigator.serviceWorker.register("/sw.js");
    const reg = await navigator.serviceWorker.ready;

    // Get VAPID public key from server
    const token = localStorage.getItem("jwt") || "";
    const keyResp = await fetch("/api/push/vapid-public-key", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!keyResp.ok) throw new Error("Failed to get VAPID key");
    const { publicKey } = await keyResp.json();

    // Convert VAPID key to Uint8Array
    const applicationServerKey = urlBase64ToUint8Array(publicKey);

    // Subscribe to push
    const subscription = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey,
    });

    // Send subscription to server
    const subKeys = (subscription as any).keys || {};
    const subData: PushSubscriptionData = {
      endpoint: subscription.endpoint,
      keys: {
        p256dh: subKeys.p256dh || "",
        auth: subKeys.auth || "",
      },
    };

    const resp = await fetch("/api/push/subscribe", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(subData),
    });

    if (!resp.ok) throw new Error("Failed to subscribe on server");
    setSubscribed(true);
  }, [supported]);

  const unsubscribe = useCallback(async () => {
    if (!supported) return;

    const reg = await navigator.serviceWorker.ready;
    const subscription = await reg.pushManager.getSubscription();
    if (!subscription) return;

    await subscription.unsubscribe();

    // Notify server
    const token = localStorage.getItem("jwt") || "";
    const subKeys = (subscription as any).keys || {};
    await fetch("/api/push/unsubscribe", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        endpoint: subscription.endpoint,
        keys: {
          p256dh: subKeys.p256dh || "",
          auth: subKeys.auth || "",
        },
      }),
    });

    setSubscribed(false);
  }, [supported]);

  const sendTest = useCallback(async () => {
    const token = localStorage.getItem("jwt") || "";
    const resp = await fetch("/api/push/test", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) throw new Error("Failed to send test");
  }, []);

  return { supported, subscribed, permission, subscribe, unsubscribe, sendTest };
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}
