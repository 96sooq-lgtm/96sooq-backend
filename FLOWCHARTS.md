# 96sooq Flowcharts

## 1. Overall System Architecture

```mermaid
graph TD
    User[Mobile/Web User] -->|HTTPS| API[FastAPI Backend]
    API -->|Auth| OAuth[Google/Apple/FB]
    API -->|Queries| DB[(Supabase PostgreSQL)]
    API -->|Images| Storage[File Storage]
    
    subgraph Core Features
        Auth --> Categories
        Categories --> Listings
        Listings --> Store[Stores]
        Listings --> Payment[Payment Gateway]
    end
    
    subgraph Interactions
        User -->|Chat| ChatSystem
        User -->|Review| ReviewSystem
        User -->|Ads| AdSystem
    end
    
    API -->|Approvals| Admin[Admin Panel]
```

## 2. Authentication Flow (Two-Step Social Login)

```mermaid
sequenceDiagram
    participant User
    participant App
    participant Backend
    participant DB

    User->>App: Click 'Sign in with Google'
    App->>App: Get Google Token
    App->>Backend: POST /oauth/check-user
    Backend->>DB: Check by provider_id
    
    rect rgb(200, 255, 200)
        Note over Backend, DB: Scenario A: User Exists
        DB-->>Backend: User Found
        Backend-->>App: { exists: true, token: "JWT" }
        App->>User: Redirect to Home
    end
    
    rect rgb(255, 200, 200)
        Note over Backend, DB: Scenario B: New User
        DB-->>Backend: User Not Found
        Backend-->>App: { exists: false }
        App->>User: Show "Complete Profile" Form
        User->>App: Enters Name & Phone
        App->>Backend: POST /oauth/complete-profile
        Backend->>DB: Create User
        Backend-->>App: { token: "JWT" }
        App->>User: Redirect to Home
    end
```

## 3. Listing Creation & Payment Flow

```mermaid
flowchart TD
    Start[User Clicks 'Sell'] --> SelectCat[Select Category]
    SelectCat --> LeafCheck{Is Leaf?}
    LeafCheck -- No --> SelectSub[Select Sub-Category] --> LeafCheck
    LeafCheck -- Yes --> FetchSchema[Fetch Attributes Schema]
    FetchSchema --> BuildForm[Build Dynamic Form]
    BuildForm --> UserFill[User Fills Details]
    UserFill --> CheckCount[Check User Listing Count]
    
    CheckCount -- First Listing --> Free[Free Post]
    CheckCount -- 2nd+ Listing --> PickPlan[Show Pricing Plans]
    
    PickPlan --> UserPays[User Pays]
    UserPays -->|Success| SubmitPaid[Submit with plan_id]
    Free --> SubmitFree[Submit with plan_id=null]
    
    SubmitPaid --> DBInsert
    SubmitFree --> DBInsert
    
    DBInsert[Insert Listing to DB] --> SetStatus[Status = pending_approval]
    SetStatus --> AdminQueue[Admin Moderation Queue]
    
    AdminQueue -->|Admin Approves| Active[Active (Visible)]
    AdminQueue -->|Admin Rejects| Rejected[Rejected (Hidden)]
```

## 4. Chat & Negotiation Flow

```mermaid
sequenceDiagram
    participant Buyer
    participant Backend
    participant Seller
    
    Buyer->>Backend: POST /chat/conversations (listing_id)
    Backend->>Seller: Notify New Conversation (Push)
    
    Buyer->>Backend: POST /chat/messages (Offer 500 AED?)
    Backend->>Seller: Incoming Message
    
    Seller->>Backend: GET /chat/conversations/{id}/messages
    Seller->>Backend: POST /chat/messages (Agreed!)
    
    Note over Buyer, Seller: Deal Reached
    
    Seller->>Backend: PUT /listings/{id}/status (Sold)
    Backend-->>Buyer: Listing marked as Sold
```

## 5. Admin Moderation Flow

```mermaid
stateDiagram-v2
    [*] --> Pending
    
    state Pending {
        [*] --> ReviewQueue
        ReviewQueue --> CheckImages
        ReviewQueue --> CheckContent
    }
    
    Pending --> Active: Approve
    Pending --> Rejected: Reject
    
    Active --> Sold: User Marks Sold
    Active --> Expired: Time limit reached
    
    Rejected --> [*]
    Sold --> [*]
```
