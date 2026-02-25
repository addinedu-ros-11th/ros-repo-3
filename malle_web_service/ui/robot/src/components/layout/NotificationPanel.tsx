import { useRobotStore } from '@/stores/robotStore';
import type { NotificationCategory } from '@/types/robot';

export function NotificationPanel() {
  const { notifications, notificationPanelOpen, toggleNotificationPanel, markNotificationRead, markAllNotificationsRead } = useRobotStore();

  const getCategoryIcon = (category: NotificationCategory) => {
    switch (category) {
      case 'NAVIGATION': return 'navigation';
      case 'LOCKBOX': return 'lock';
      case 'PICKUP': return 'shopping_bag';
      case 'SYSTEM': return 'settings';
    }
  };

  const getCategoryColor = (category: NotificationCategory) => {
    switch (category) {
      case 'NAVIGATION': return 'bg-blue-100 dark:bg-blue-900/30 text-blue-600';
      case 'LOCKBOX': return 'bg-green-100 dark:bg-green-900/30 text-green-600';
      case 'PICKUP': return 'bg-pink-100 dark:bg-pink-900/30 text-pink-600';
      case 'SYSTEM': return 'bg-slate-100 dark:bg-slate-800 text-slate-600';
    }
  };

  const formatTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return date.toLocaleDateString();
  };

  const unreadCount = notifications.filter(n => !n.read).length;

  if (!notificationPanelOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/20 z-30"
        onClick={toggleNotificationPanel}
      />
      
      {/* Panel */}
      <div className="notification-panel animate-slide-in-right">
        <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-foreground">Notifications</h2>
            {unreadCount > 0 && (
              <p className="text-sm text-muted-foreground">{unreadCount} unread</p>
            )}
          </div>
          <div className="flex items-center space-x-2">
            {unreadCount > 0 && (
              <button 
                onClick={markAllNotificationsRead}
                className="text-xs text-primary font-medium hover:underline"
              >
                Mark all as read
              </button>
            )}
            <button 
              onClick={toggleNotificationPanel}
              className="p-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <span className="material-icons-round text-slate-500">close</span>
            </button>
          </div>
        </div>

        <div className="overflow-y-auto hide-scrollbar h-[calc(100%-5rem)]">
          {notifications.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <span className="material-icons-round text-4xl mb-2">notifications_off</span>
              <p>No notifications</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {notifications.map((notification) => (
                <div
                  key={notification.id}
                  onClick={() => markNotificationRead(notification.id)}
                  className={`p-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors ${!notification.read ? 'notification-unread' : ''}`}
                >
                  <div className="flex items-start space-x-3">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${getCategoryColor(notification.category)}`}>
                      <span className="material-icons-round text-lg">{getCategoryIcon(notification.category)}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-foreground text-sm">{notification.title}</p>
                      <p className="text-sm text-muted-foreground">{notification.description}</p>
                      <p className="text-xs text-slate-400 mt-1">{formatTime(notification.timestamp)}</p>
                    </div>
                    {!notification.read && (
                      <span className="w-2 h-2 rounded-full bg-primary flex-shrink-0 mt-2" />
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
