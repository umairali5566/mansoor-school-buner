import React from 'react';

const Card = ({
  title,
  children,
  className = '',
  headerAction,
  ...props
}) => {
  return (
    <div
      className={`bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition-shadow duration-200 ${className}`}
      {...props}
    >
      {(title || headerAction) && (
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          {title && (
            <h3 className="text-lg font-semibold text-gray-900" id={`card-title-${title.replace(/\s+/g, '-').toLowerCase()}`}>
              {title}
            </h3>
          )}
          {headerAction && (
            <div className="flex space-x-2">
              {headerAction}
            </div>
          )}
        </div>
      )}
      <div className="p-6">
        {children}
      </div>
    </div>
  );
};

const StatCard = ({
  title,
  value,
  icon,
  trend,
  className = ''
}) => {
  return (
    <Card className={`hover:scale-105 transition-transform duration-200 ${className}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {trend && (
            <p className={`text-sm ${trend.isPositive ? 'text-green-600' : 'text-red-600'}`}>
              {trend.isPositive ? '↑' : '↓'} {trend.value} from last month
            </p>
          )}
        </div>
        <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center">
          <i className={`bi ${icon} text-primary text-xl`} aria-hidden="true"></i>
        </div>
      </div>
    </Card>
  );
};

export { Card, StatCard };