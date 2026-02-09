"""
Custom Email Backend that works around SSL certificate issues on Windows.
"""
import ssl
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend


class CustomEmailBackend(SMTPBackend):
    """
    Email backend that uses a relaxed SSL context to avoid 
    certificate verification issues on Windows.
    """
    
    def open(self):
        if self.connection:
            return False
        
        try:
            # Create a relaxed SSL context
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
            
            # Call parent open with our custom SSL context
            return super().open()
        except Exception:
            if not self.fail_silently:
                raise
            return False
