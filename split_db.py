"""Split database_v3.py into domain submodules"""
import ast, re, os, textwrap

with open('database_v3.py', 'r', encoding='utf-8') as f:
    source = f.read()
    lines = source.split('\n')

tree = ast.parse(source)

# Extract all top-level functions with their full source
func_nodes = []
for node in ast.iter_child_nodes(tree):
    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        end = node.end_lineno if hasattr(node, 'end_lineno') and node.end_lineno else node.lineno
        func_lines = lines[node.lineno - 1:end]
        func_source = '\n'.join(func_lines) + '\n'
        func_nodes.append({
            'name': node.name,
            'source': func_source,
        })

func_map = {f['name']: f for f in func_nodes}

modules = {
    'connection.py': [
        'get_conn', 'transaction', 'clear_query_cache', 'init_db', 'init_v3_tables', 'init_system_templates',
    ],
    'ledger.py': [
        'create_ledger', 'get_ledgers', 'get_ledger', 'update_ledger', 'delete_ledger',
        'backup_ledger_to_json', 'restore_ledger_from_json', 'get_aux_ledger', 'get_account_ledger',
    ],
    'account.py': [
        'get_account_balances', 'get_accounts', 'add_account', 'search_accounts_by_kw',
        'update_bank_account', 'delete_bank_account', 'create_bank_account', 'get_bank_accounts',
        'import_bank_statement', 'get_default_accounts', 'import_accounts_from_template',
        'get_account_suggestions', 'get_avg_amount_for_account',
        'auto_match_bank_statement', 'get_bank_reconciliation', 'match_bank_statement',
        'unmatch_bank_statement', 'get_unmatched_items', 'get_bank_statements_list',
    ],
    'voucher.py': [
        'create_voucher', 'update_voucher', 'post_voucher', 'approve_voucher', 'reject_voucher',
        'reverse_voucher', 'delete_voucher', 'get_vouchers', 'get_voucher_detail',
        'generate_voucher_from_text', 'get_voucher_templates', 'create_voucher_template',
        'update_voucher_template', 'delete_voucher_template', 'submit_for_review',
        'get_voucher_workflow', 'get_scheduled_vouchers', 'add_scheduled_voucher',
        'run_scheduled_voucher', 'link_invoice_voucher', 'get_invoice_vouchers',
        'import_vouchers_from_excel', 'generate_composite_voucher', 'parse_complex_voucher',
        'search_vouchers', 'search_vouchers_by_aux', 'search_voucher_history_v2',
        'save_voucher_template',
    ],
    'report.py': [
        'get_balance_sheet', 'get_income_statement', 'export_balance_sheet_csv',
        'export_income_statement_csv', 'export_balance_sheet_pdf', 'export_income_statement_pdf',
        'export_account_balances_csv', 'export_account_balances_pdf',
        'export_vouchers_csv', 'export_vouchers_pdf', '_flatten_bs', '_get_cjk_font',
    ],
    'auth.py': [
        'hash_password', 'verify_password', 'create_user', 'authenticate', 'get_users',
        'update_user', 'delete_user', 'change_password', 'check_permission',
    ],
    'period.py': [
        'get_close_period_checklist', 'close_period', 'get_period_status', 'reverse_close_period',
        'set_opening_balance', 'get_opening_balance',
    ],
    'budget.py': [
        'get_budgets', 'set_budget', 'get_budget_execution', 'get_budget_summary', 'check_budget_exceeded',
    ],
    'tax.py': [
        'get_tax_config', 'set_tax_config', 'get_tax_rates', 'add_tax_rate', 'get_tax_summary', 'get_tax_detail',
    ],
    'cash_flow.py': [
        'get_cash_flow_categories', 'add_cash_flow_category', 'get_cash_flow_statement',
        '_infer_cash_flow', 'init_cash_flow_categories', '_init_default_cash_flow_categories',
        'get_cash_flow_statement_direct',
    ],
    'fixed_asset.py': [
        'create_fixed_asset', 'get_fixed_assets', 'get_fixed_asset', 'calculate_depreciation',
        'batch_calculate_depreciation', 'dispose_asset',
    ],
    'invoice.py': [
        'extract_invoice_info', 'get_invoices', 'add_invoice', 'get_invoice_summary', 'ocr_recognize_invoice',
    ],
    'multi_currency.py': [
        '_init_default_currencies', '_init_default_exchange_rates', 'set_exchange_rate',
        'get_exchange_rate', 'convert_currency',
    ],
    'ai.py': [
        'get_ai_rules_complex', 'add_ai_rules_complex', 'delete_ai_rules_complex',
        'toggle_ai_rules_complex', 'query_db', '_init_complex_rules',
    ],
    'classification.py': [
        'classify_transaction', '_match_history', '_detect_anomaly', 'batch_classify',
        'get_classification_rules', 'parse_bank_csv', 'save_classified_transactions',
    ],
    'auxiliary.py': [
        'create_auxiliary', 'get_auxiliaries', 'update_auxiliary', 'delete_auxiliary',
        'save_aux_mapping', 'get_aux_mapping', 'get_aux_balance', 'multi_aux_search',
    ],
    'audit.py': [
        'add_audit_log', 'get_audit_logs', 'add_workflow_log',
    ],
    'backup.py': [
        'backup_database', 'backup_full_database', 'restore_database',
    ],
    'dashboard.py': [
        'get_dashboard_kpi', 'get_monthly_trend', 'get_expense_breakdown',
        'get_period_compare_income', 'get_period_compare_balance',
    ],
    'init_data.py': [
        '_init_chart_of_accounts', '_init_missing_accounts',
    ],
}

os.makedirs('database', exist_ok=True)

# Write each module
all_exports = []
for mod_name, fnames in modules.items():
    filepath = os.path.join('database', mod_name)
    mod_short = mod_name.replace('.py', '')

    parts = []
    parts.append(f'"""Database module: {mod_short} domain"""')
    parts.append('')
    if mod_name == 'connection.py':
        # Prepend the original imports and DB_PATH
        header = '''"""
AI 财务系统 — 数据库模块 v2
拆分后: database/connection.py — 核心连接与初始化
"""

import sqlite3
import os
import functools
from contextlib import contextmanager
from datetime import datetime, date
from enum import Enum

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "finance_v2.db")

'''
        parts = [header]
    else:
        parts.append('from .connection import get_conn, transaction, DB_PATH')
        parts.append('')

    for fname in fnames:
        if fname in func_map:
            parts.append(func_map[fname]['source'])
            all_exports.append(fname)

    content = '\n'.join(parts)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Created: {filepath} ({len(fnames)} funcs)')

# Write __init__.py
init_parts = ['"""Database package — split from database_v3.py"""', '', '# flake8: noqa: F401']
for mod_name, fnames in modules.items():
    mod_short = mod_name.replace('.py', '')
    init_parts.append(f'from .{mod_short} import {", ".join(fnames)}')
init_parts.append('')
init_parts.append(f'__all__ = {repr(all_exports)}')
init_parts.append('')

with open('database/__init__.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(init_parts))
print(f'Created: database/__init__.py ({len(all_exports)} exports)')

# Rewrite database_v3.py as a thin wrapper for backward compat
wrapper = '''"""
AI 财务系统 — 数据库模块 v3

向后兼容包装器 — 所有函数已拆分为 database/ 子模块。
新代码请直接从 database 包导入：
    from database import get_conn, create_v3_tables, ...
"""
from database import *
from database import __all__
'''

with open('database_v3.py', 'w', encoding='utf-8') as f:
    f.write(wrapper)
print('Rewrote: database_v3.py (backward-compat wrapper)')
