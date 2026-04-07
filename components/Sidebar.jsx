import React from 'react';

const Sidebar = ({ isOpen, user, navigation }) => {
  return (
    <aside
      className={`fixed left-0 top-0 z-40 h-screen w-64 bg-white border-r border-gray-200 shadow-xl transform transition-transform duration-300 ${
        isOpen ? 'translate-x-0' : '-translate-x-full'
      } md:translate-x-0`}
      aria-label="Primary navigation"
      role="navigation"
    >
      <div className="flex flex-col h-full">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
              <i className="bi bi-mortarboard-fill text-white text-xl" aria-hidden="true"></i>
            </div>
            <div>
              <span className="text-xl font-bold text-textPrimary">SAAMS</span>
              <span className="text-xs text-textSecondary">Premium SaaS</span>
            </div>
          </div>
        </div>
        <nav className="flex-1 px-6 py-4" aria-label="Main navigation">
          <ul className="space-y-2">
            {navigation.map((item) => (
              <li key={item.name}>
                <a
                  href={item.href}
                  className={`flex items-center space-x-3 px-3 py-2 rounded-lg text-textPrimary hover:bg-gray-100 transition-all duration-300 ${
                    item.current ? 'bg-primary text-white' : ''
                  }`}
                  aria-current={item.current ? 'page' : undefined}
                >
                  <i className={`bi ${item.icon}`} aria-hidden="true"></i>
                  <span>{item.name}</span>
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="p-6 border-t border-gray-200">
          <div className="flex items-center space-x-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center">
              {user.image ? (
                <img src={user.image} alt={`${user.name}'s avatar`} className="w-full h-full rounded-full object-cover" />
              ) : (
                <i className="bi bi-person-fill text-white" aria-hidden="true"></i>
              )}
            </div>
            <div>
              <p className="text-textPrimary font-medium text-sm">{user.name}</p>
              <p className="text-textSecondary text-xs">{user.role}</p>
            </div>
          </div>
          <form method="post" action="/logout">
            <button
              type="submit"
              className="w-full bg-danger hover:bg-red-600 text-white px-4 py-2 rounded-lg transition-all duration-300 flex items-center space-x-2"
              aria-label="Logout"
            >
              <i className="bi bi-box-arrow-right" aria-hidden="true"></i>
              <span>Logout</span>
            </button>
          </form>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;