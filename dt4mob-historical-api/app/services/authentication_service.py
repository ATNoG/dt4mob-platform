import logging
from fastapi import Header, HTTPException, status

from typing import Optional


class NginxAuthenticationService:
    def __call__(self, 
                x_forwarded_user: Optional[str] = Header(None,include_in_schema=False),
                x_ditto_pre_authenticated: Optional[str] = Header(None,include_in_schema=False)
    ) -> str:
        if not x_forwarded_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Direct access not allowed."
            )
        
        user = x_ditto_pre_authenticated.replace("nginx:", "") if x_ditto_pre_authenticated else x_forwarded_user
        logging.info(f"Authenticated user: {user}")

        return user