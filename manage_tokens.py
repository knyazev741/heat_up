#!/usr/bin/env python3
"""
CLI tool to manage API tokens
"""
import sys
import argparse
from auth import create_token, revoke_token, list_tokens


def cmd_create(args):
    """Create a new API token"""
    token = create_token(args.name, args.description or "")
    print(f"\n✅ Created new API token: {args.name}")
    print(f"\n🔑 Token (save this, it won't be shown again!):")
    print(f"\n    {token}\n")
    print(f"Use this token in the Authorization header:")
    print(f"    Authorization: Bearer {token}\n")


def cmd_list(args):
    """List all tokens"""
    tokens = list_tokens()
    
    if not tokens:
        print("\n📋 No tokens found.\n")
        return
    
    print(f"\n📋 API Tokens ({len(tokens)}):\n")
    for token in tokens:
        print(f"  • {token['name']}")
        print(f"    Hash: {token['token_hash']}")
        if token['description']:
            print(f"    Description: {token['description']}")
        print(f"    Created: {token['created_at']}")
        print(f"    Last used: {token['last_used'] or 'Never'}")
        print(f"    Usage count: {token['usage_count']}")
        print()


def cmd_revoke(args):
    """Revoke a token"""
    if revoke_token(args.token):
        print(f"\n✅ Token revoked successfully.\n")
    else:
        print(f"\n❌ Token not found.\n")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Manage API tokens for Heat Up service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a new token
  python manage_tokens.py create --name "production" --description "Production API access"
  
  # List all tokens
  python manage_tokens.py list
  
  # Revoke a token
  python manage_tokens.py revoke <token>
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    subparsers.required = True
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new API token')
    create_parser.add_argument('--name', required=True, help='Token name/identifier')
    create_parser.add_argument('--description', help='Token description')
    create_parser.set_defaults(func=cmd_create)
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all API tokens')
    list_parser.set_defaults(func=cmd_list)
    
    # Revoke command
    revoke_parser = subparsers.add_parser('revoke', help='Revoke an API token')
    revoke_parser.add_argument('token', help='Token to revoke (plain text or hash)')
    revoke_parser.set_defaults(func=cmd_revoke)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()

