# Platinum Project - Portal Approvals

![Odoo Version](https://img.shields.io/badge/Odoo-18.0-blue.svg)
![License](https://img.shields.io/badge/License-LGPL--3-green.svg)
![Version](https://img.shields.io/badge/Version-18.0.1.0.0-orange.svg)

## Overview

The **Platinum Project - Portal Approvals** module extends Odoo's standard approval functionality to provide a comprehensive employee portal interface for approval requests. This module bridges the gap between backend approval management and frontend employee access, enabling seamless approval workflows without requiring backend user access.

## Key Features

- **Portal Access**: Employees can submit approval requests through a dedicated portal interface
- **Employee-Based Ownership**: Request ownership tied to employees rather than just users
- **Mobile-Responsive Design**: Fully responsive portal interface optimized for mobile devices
- **Budget Integration**: Real-time budget validation and tracking
- **Department Routing**: Intelligent approval routing based on department hierarchy
- **Audit Trail**: Complete tracking and audit trail for all requests
- **Email Notifications**: Automated notifications at each workflow step

## Module Dependencies

This module depends on the following Odoo modules:

- `approvals` - Core approval functionality
- `hr` - Employee data and department management
- `portal` - Portal access framework
- `purchase` - Purchase order integration
- `stock` - Inventory management integration
- `account` - Budget tracking via analytic accounts

## Installation

1. Clone or copy this module to your Odoo addons directory:
   ```bash
   cp -r platinum_proj /path/to/odoo/addons/
   ```

2. Update your addons list in Odoo:
   - Go to **Apps** > **Update Apps List**

3. Install the module:
   - Search for "Platinum Project - Portal Approvals"
   - Click **Install**

## Configuration

### Initial Setup

1. **Employee Configuration**:
   - Ensure all employees have associated portal users
   - Configure department hierarchies in HR module
   - Set up approval categories specific to your organization

2. **Portal Access**:
   - Configure portal user groups and permissions
   - Set up email templates for notifications
   - Configure approval workflows per category

3. **Budget Integration**:
   - Set up analytic accounts for budget tracking
   - Configure budget limits per department/category

### Security Configuration

The module includes comprehensive security rules:
- Portal users can only access their own requests
- Department managers can approve requests within their scope
- Admin users have full access to all approval data

## Usage

### For Employees

1. **Access Portal**: Log into the Odoo portal with your credentials
2. **Submit Request**: Navigate to Approvals section and create new request
3. **Track Progress**: Monitor request status and approval progress
4. **Receive Notifications**: Get email updates at each workflow step

### For Approvers

1. **Review Requests**: Access pending requests through backend or portal
2. **Budget Validation**: Review budget impact before approval
3. **Approve/Reject**: Make approval decisions with comments
4. **Monitor Workflows**: Track departmental approval metrics

## Technical Details

### File Structure

```
platinum_proj/
├── __init__.py
├── __manifest__.py
├── controllers/           # Portal controllers
├── data/                 # Data files and cron jobs
├── models/               # Python models
├── security/             # Access control files
├── static/               # CSS, JS, and images
│   └── src/
│       ├── js/          # JavaScript files
│       └── scss/        # Stylesheet files
└── views/               # XML view definitions
```

### Key Models

- **approval.request** (extended): Enhanced with portal functionality
- **hr.employee** (extended): Added approval-related fields
- Portal controllers for frontend access

## Development

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

### Code Style

This project follows Odoo's coding standards:
- Python code follows PEP 8
- XML files use proper indentation
- JavaScript follows ES6+ standards

## Support

For issues, questions, or contributions:

1. Check the existing documentation
2. Review the project plan in `platinum_project_plan.md`
3. Contact the development team

## License

This project is licensed under LGPL-3 - see the LICENSE file for details.

## Version History

- **18.0.1.0.0** - Initial release
  - Portal approval interface
  - Employee-based request management
  - Budget integration
  - Mobile-responsive design

## Related Documentation

- [Platinum Project Plan](platinum_project_plan.md) - Detailed project specifications
- Odoo Official Documentation - [Approvals Module](https://www.odoo.com/documentation/18.0/applications/productivity/approvals.html)
- Odoo Portal Development - [Portal Framework](https://www.odoo.com/documentation/18.0/developer/reference/backend/portal.html)
