# Related Tickets Implementation
# Phase 1: Rule-based approach with text similarity

from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
import re
from collections import Counter
from .models import Ticket


class RelatedTicketsFinder:
    """Find related tickets using multiple strategies"""

    def __init__(self, ticket):
        self.ticket = ticket
        self.related_tickets = []

    def find_related_tickets(self, max_results=5):
        """Main method to find related tickets"""
        related = []

        # Strategy 1: Same category
        related.extend(self._find_by_category())

        # Strategy 2: Referenced ticket numbers
        related.extend(self._find_by_references())

        # Strategy 3: Keyword similarity
        related.extend(self._find_by_keywords())

        # Strategy 4: Same creator with similar issues
        related.extend(self._find_by_creator_pattern())

        # Remove duplicates and current ticket
        seen = set()
        unique_related = []
        for ticket_id, score, reason in related:
            if ticket_id not in seen and ticket_id != self.ticket.id:
                seen.add(ticket_id)
                unique_related.append((ticket_id, score, reason))

        # Sort by score and return top results
        unique_related.sort(key=lambda x: x[1], reverse=True)
        return unique_related[:max_results]

    def _find_by_category(self):
        """Find tickets in same category"""
        if not self.ticket.category:
            return []

        related = (
            Ticket.objects.filter(category=self.ticket.category)
            .exclude(id=self.ticket.id)
            .values_list("id", flat=True)[:10]
        )

        return [
            (tid, 0.7, f"Same category: {self.ticket.category.name}") for tid in related
        ]

    def _find_by_references(self):
        """Find tickets referenced in descriptions/comments"""
        related = []

        # Look for ticket number patterns like #123, Ticket 123, etc.
        text_to_search = f"{self.ticket.title} {self.ticket.description}"

        # Add comment text
        for comment in self.ticket.comments.all():
            text_to_search += f" {comment.content}"

        # Find ticket number patterns
        patterns = [
            r"#(\d+)",
            r"[Tt]icket\s+#?(\d+)",
            r"[Ii]ssue\s+#?(\d+)",
        ]

        referenced_ids = set()
        for pattern in patterns:
            matches = re.findall(pattern, text_to_search)
            referenced_ids.update([int(m) for m in matches])

        # Check if these tickets exist
        existing_tickets = (
            Ticket.objects.filter(id__in=referenced_ids)
            .exclude(id=self.ticket.id)
            .values_list("id", flat=True)
        )

        return [(tid, 0.9, "Referenced in ticket") for tid in existing_tickets]

    def _find_by_keywords(self):
        """Find tickets with similar keywords"""
        # Extract keywords from title and description
        ticket_text = f"{self.ticket.title} {self.ticket.description}".lower()

        # Simple keyword extraction (remove common words)
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "this",
            "that",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
        }

        words = re.findall(r"\b\w+\b", ticket_text)
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]

        if not keywords:
            return []

        # Find tickets with similar keywords
        related = []
        for keyword in keywords[:5]:  # Top 5 keywords
            similar_tickets = (
                Ticket.objects.filter(
                    Q(title__icontains=keyword) | Q(description__icontains=keyword)
                )
                .exclude(id=self.ticket.id)
                .values_list("id", flat=True)[:5]
            )

            for tid in similar_tickets:
                related.append((tid, 0.5, f"Similar keyword: {keyword}"))

        return related

    def _find_by_creator_pattern(self):
        """Find tickets from same creator with similar patterns"""
        # Recent tickets from same creator
        recent_date = timezone.now() - timedelta(days=30)

        creator_tickets = (
            Ticket.objects.filter(
                created_by=self.ticket.created_by, created_at__gte=recent_date
            )
            .exclude(id=self.ticket.id)
            .values_list("id", flat=True)[:5]
        )

        return [(tid, 0.4, "Same creator (recent)") for tid in creator_tickets]


# Simple text similarity using basic algorithms
class TextSimilarity:
    """Simple text similarity without heavy ML dependencies"""

    @staticmethod
    def jaccard_similarity(text1, text2):
        """Calculate Jaccard similarity between two texts"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0

    @staticmethod
    def get_similar_tickets(target_ticket, threshold=0.3):
        """Find tickets similar to target using Jaccard similarity"""
        target_text = f"{target_ticket.title} {target_ticket.description}"
        similar_tickets = []

        # Compare with other tickets
        for ticket in Ticket.objects.exclude(id=target_ticket.id):
            ticket_text = f"{ticket.title} {ticket.description}"
            similarity = TextSimilarity.jaccard_similarity(target_text, ticket_text)

            if similarity > threshold:
                similar_tickets.append(
                    (ticket.id, similarity, f"Text similarity: {similarity:.2f}")
                )

        return similar_tickets


# Usage example:
def get_related_tickets_for_display(ticket, user=None):
    """Main function to get related tickets for display"""
    finder = RelatedTicketsFinder(ticket)
    related_data = finder.find_related_tickets(max_results=5)

    # Convert to actual ticket objects
    related_tickets = []
    for ticket_id, score, reason in related_data:
        try:
            related_ticket = Ticket.objects.get(id=ticket_id)

            # Check if user has access to this related ticket
            if user:
                from .utils import user_can_access_ticket

                if not user_can_access_ticket(user, related_ticket):
                    continue  # Skip this ticket if user doesn't have access

            related_tickets.append(
                {"ticket": related_ticket, "score": score, "reason": reason}
            )
        except Ticket.DoesNotExist:
            continue

    return related_tickets
